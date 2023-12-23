"""Syncs photos from an Adobe Lightroom gallery to a Google Drive folder."""

import io
import json
import os
import tempfile
import webbrowser
import zipfile
import click
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
from tqdm import tqdm


def setup_google_drive_credentials() -> None:
    """
    Guides the user through the process of setting up Google Drive API credentials.
    """
    print(
        "To use this script, you need to enable the Google Drive "
        "API and download the credentials file."
    )
    print("Please follow these steps:\n")

    print(
        "1. Go to the Google Developers Console: https://console.developers.google.com/"
    )
    print("2. Create a new project or select an existing one.")
    print(
        "3. Navigate to 'Library' and enable the 'Google Drive API' for your project."
    )
    print(
        "4. Go to 'Credentials', click on 'Create credentials', and select 'OAuth client ID'."
    )
    print("5. If prompted, configure the OAuth consent screen.")
    print(
        "6. Select 'Desktop app' as the Application type, give it a name, and click 'Create'."
    )
    print(
        "7. Download the JSON file by clicking on the download "
        "button next to the created OAuth client."
    )
    print(
        "8. Rename the downloaded file to 'token.json' and place "
        "it in the directory of this script."
    )

    input("\nPress Enter after you have completed these steps...")

    # Optionally open the Google Developers Console automatically
    open_console = input(
        "Would you like to open the Google Developers "
        "Console in your web browser now? (y/n): "
    )
    if open_console.lower() == "y":
        webbrowser.open("https://console.developers.google.com/")


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


def get_google_service(service_name) -> Resource:
    """Sets up the Google Drive API client."""
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/photoslibrary"
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
    return build(service_name, "v3", credentials=creds)


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
    print("Upload complete.")


def get_google_token() -> str:
    """Returns the token from the 'token.json' file."""
    get_google_service("drive")
    with open("token.json", "r", encoding="utf-8") as token_file:
        return json.load(token_file)["token"]


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
    prompt="Google Drive Folder ID",
    help="The ID of the Google Drive folder to upload to.",
)
def main(gallery_url: str, folder_id: str) -> None:
    """
    Main function to orchestrate the download, extraction, and uploading process.
    Checks for the existence of 'token.json' and runs setup if it doesn't exist.
    """
    if not os.path.exists("token.json"):
        setup_google_drive_credentials()

    try:
        download_url = generate_download_url(gallery_url)
    except ValueError as e:
        print(f"Error: {e}")
        return

    with tempfile.TemporaryDirectory() as extract_to:
        download_and_extract_zip(download_url, extract_to)

        drive_service = get_google_service("drive")

        upload_files_to_drive(drive_service, folder_id, extract_to)

        print("Upload Complete")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
