"""Syncs photos from an Adobe Lightroom gallery to a Google Drive folder."""

import io
import os
import webbrowser
import zipfile
import click
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import requests



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
    response = requests.get(url, timeout=10)
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        zip_file.extractall(extract_to)


def setup_google_drive_api() -> Resource:
    """Sets up the Google Drive API client."""
    scopes = [
        "https://www.googleapis.com/auth/drive"
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
    return build("drive", "v3", credentials=creds)


def create_drive_folder(service: Resource, folder_name: str) -> str:
    """Creates a folder in Google Drive and returns its ID."""
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return folder.get("id")


def upload_files_to_drive(service: Resource, folder_id: str, directory: str) -> None:
    """Uploads files from a directory to a Google Drive folder."""
    for filename in os.listdir(directory):
        if filename.endswith(".jpg"):
            file_metadata = {"name": filename, "parents": [folder_id]}
            media = MediaFileUpload(f"{directory}/{filename}", mimetype="image/jpeg")
            service.files().create(
                body=file_metadata, media_body=media, fields="id"
            ).execute()


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
    "--folder_name",
    default="Photos",
    help="Name of the folder to create in Google Drive.",
)
def main(gallery_url: str, folder_name: str) -> None:
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

    extract_to = "photos"
    download_and_extract_zip(download_url, extract_to)

    service = setup_google_drive_api()
    folder_id = create_drive_folder(service, folder_name)

    upload_files_to_drive(service, folder_id, extract_to)

    print("Upload Complete")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
