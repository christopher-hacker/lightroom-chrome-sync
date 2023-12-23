# README for Lightroom-GoogleDrive Sync

## Description
This script synchronizes photos from an Adobe Lightroom gallery to a Google Drive folder or a Google Photos album. It automates the process of downloading photos from Adobe Lightroom, and uploading them to Google Drive or Google Photos.

## Requirements
- Python 3.10 or higher
- Dependencies listed in `pyproject.toml`

## Installation
1. Clone the repository.
2. Navigate to the project directory:
   ```
   cd lightroom-googledrive-sync
   ```
3. Install the required packages using Poetry:
   ```
   poetry install
   ```

## Setup
Before using the script, follow these steps to set up Google Drive API credentials:
1. Enable the Google Drive API and download the credentials file.
2. Rename the downloaded file to `credentials.json` and place it in the project directory.
3. Run the script for the first time, and it will guide you through the process of authorizing access to your Google account.

## Usage
Run the script with the following command:
```
poetry run python main.py --gallery_url [LIGHTROOM_GALLERY_URL] [--folder_id GOOGLE_DRIVE_FOLDER_ID] [--album_name GOOGLE_PHOTOS_ALBUM_NAME]
```
Options:
- `--gallery_url`: URL of the Adobe Lightroom gallery.
- `--folder_id` (optional): ID of the Google Drive folder to upload to.
- `--album_name` (optional): Name of the Google Photos album to upload to.

Note: At least one of `--folder_id` or `--album_name` must be specified.

## Example
```
poetry run python main.py --gallery_url "https://lightroom.adobe.com/gallery/12345/albums/67890/assets" --folder_id "abcd1234"
```

This command will download photos from the specified Lightroom gallery and upload them to the specified Google Drive folder.

## Contributing
For contributions and bug reports, please open an issue or pull request in the repository.
