"""Syncs photos from an Adobe Lightroom gallery to a Google Drive folder."""

import io
import json
import os
import tempfile
from typing import Dict, Any
import zipfile
import click
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
from requests.exceptions import HTTPError
from tqdm import tqdm


def download_and_extract_zip(url: str, extract_to: str) -> None:
    """Downloads and extracts a ZIP file from a URL."""
    try:
        response = requests.get(url, timeout=10)
        assert response.status_code == 200, f"Error: {response.status_code}"
    except requests.exceptions.RequestException as exc:
        print(f"Error: {exc}")
        return

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        zip_file.extractall(extract_to)
    print("Download and extraction complete.")


def get_google_service(service_name, service_version) -> Resource:
    """Sets up the Google Drive API client."""
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/photoslibrary",
    ]
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", scopes)
            creds = flow.run_local_server(port=0)

    with open("token.json", "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    return build(
        service_name, service_version, credentials=creds, static_discovery=False
    )


def upload_files_to_drive(service: Resource, folder_id: str, directory: str) -> None:
    """Uploads files from a directory to a Google Drive folder."""
    files = [f for f in os.listdir(directory) if f.endswith(".jpg")]
    print(f"Uploading {len(files)} files to Google Drive...")

    for filename in tqdm(files, desc="Uploading"):
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(f"{directory}/{filename}", mimetype="image/jpeg")
        service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()


def get_google_token() -> str:
    """Returns the token from the 'token.json' file."""
    get_google_service("drive", "v3")
    with open("token.json", "r", encoding="utf-8") as token_file:
        return json.load(token_file)["token"]


def find_album_by_name(service: Resource, album_name: str) -> Dict[str, Any]:
    """Search for a Google Photos album by name.

    Args:
        service (Resource): Authenticated Google Photos service object.
        album_name (str): Name of the album to search for.

    Returns:
        Dict[str, Any]: Dictionary with album details if found.

    Raises:
        AlbumNotFoundError: If the album is not found.
    """
    try:
        results = service.albums().list(pageSize=50).execute()

        while True:
            for album in results.get("albums", []):
                if album["title"].lower() == album_name.lower():
                    return album

            # Check for next page
            page_token = results.get("nextPageToken")
            if page_token:
                results = (
                    service.albums().list(pageSize=50, pageToken=page_token).execute()
                )
            else:
                break

        # If album not found, raise an error
        raise ValueError(f"Album '{album_name}' not found.")

    except Exception as exc:
        print(f"An error occurred: {exc}")
        raise


def upload_files_to_google_photos(
    token: str, album_details: Dict[str, Any], directory: str
) -> None:
    """Uploads files from a directory to a Google Photos album."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/octet-stream",
        "X-Goog-Upload-Content-Type": "image/jpeg",
        "X-Goog-Upload-Protocol": "raw",
    }

    files = [f for f in os.listdir(directory) if f.endswith(".jpg")]
    print(f"Uploading {len(files)} files to Google Photos...")

    for filename in tqdm(files, desc="Uploading"):
        file_path = os.path.join(directory, filename)

        # Upload the photo bytes to get an upload token
        with open(file_path, "rb") as photo:
            upload_response = requests.post(
                "https://photoslibrary.googleapis.com/v1/uploads",
                headers=headers,
                data=photo,
                timeout=120,
            )
            upload_response.raise_for_status()
            upload_token = upload_response.content.decode("utf-8")

        # Create a media item in Google Photos using the upload token
        create_body = {
            "newMediaItems": [
                {"description": "", "simpleMediaItem": {"uploadToken": upload_token}}
            ],
            "albumId": album_details["id"],
        }

        response = requests.post(
            "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate",
            headers={"Authorization": f"Bearer {token}"},
            json=create_body,
            timeout=120,
        )
        if response.status_code != 200:
            raise HTTPError(response, response.json())


def generate_download_url(gallery_url: str) -> str:
    """Generates a download URL from a given Adobe Lightroom gallery URL.

    Args:
        gallery_url (str): The Adobe Lightroom gallery URL in the format:
                'https://lightroom.adobe.com/gallery/[gallery_id]/albums/[album_id]/assets'

    Returns:
        str: The corresponding download URL.
    """
    parts = gallery_url.split("/")
    if len(parts) >= 8 and parts[2] == "lightroom.adobe.com" and parts[3] == "gallery":
        gallery_id = parts[4]
        album_id = parts[6]
        download_url = (
            f"https://dl.lightroom.adobe.com/spaces/{gallery_id}/"
            f"albums/{album_id}?fullsize=true"
        )
        return download_url

    raise ValueError(f"Invalid gallery URL format: {gallery_url}")


@click.command()
@click.option(
    "--gallery_url", prompt="Gallery URL", help="The Adobe Lightroom gallery URL."
)
@click.option(
    "--folder_id",
    default=None,
    help="The ID of the Google Drive folder to upload to.",
)
@click.option(
    "--album_name",
    default=None,
    help="The name of the Google Photos album to upload to.",
)
def main(
    gallery_url: str,
    folder_id: str = None,
    album_name: str = None,
) -> None:
    """
    Main function to orchestrate the download, extraction, and uploading process.
    Checks for the existence of 'token.json' and runs setup if it doesn't exist.
    """
    if not folder_id and not album_name:
        raise ValueError("At least one of folder_id or album_name must be specified.")

    try:
        download_url = generate_download_url(gallery_url)
    except ValueError as e:
        print(f"Error: {e}")
        return

    with tempfile.TemporaryDirectory() as extract_to:
        print("Downloading and extracting ZIP file...")
        download_and_extract_zip(download_url, extract_to)
        print(f"Download and extraction complete. Files saved to {extract_to}")

        if folder_id:
            print(f"Uploading to Google Drive folder {folder_id}...")
            drive_service = get_google_service("drive", "v3")
            upload_files_to_drive(drive_service, folder_id, extract_to)

        if album_name:
            print(f"Uploading to Google Photos album {album_name}...")
            photos_service = get_google_service("photoslibrary", "v1")
            token = get_google_token()
            try:
                album_details = find_album_by_name(photos_service, album_name)
            except ValueError:
                print(f"Album '{album_name}' not found. Creating a new album...")
                create_body = {"album": {"title": album_name}}
                response = photos_service.albums().create(body=create_body).execute() # pylint: disable=no-member
                album_details = response["id"]

            upload_files_to_google_photos(token, album_details, extract_to)

        print("Done!")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
