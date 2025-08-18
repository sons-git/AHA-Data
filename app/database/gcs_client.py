import uuid
import base64
import filetype
from google.cloud import storage
from google.oauth2 import service_account
from app.schemas.conversations import FileData
from app.database.redis_client import get_redis_config

# Retrieve GCS credentials and bucket name from Redis config
gcs_key_data = get_redis_config("gcs-service-key")
credentials = service_account.Credentials.from_service_account_info(gcs_key_data)
BUCKET_NAME = get_redis_config("api_keys")["BUCKET_NAME"]

async def upload_file_to_gcs(convo_id: str, file_data: FileData) -> str:
    """
    Uploads a file (base64 string or bytes) to Google Cloud Storage and returns its GCS URL.

    Args:
        convo_id (str): The conversation ID used for folder structure.
        file_data (FileData): File data object containing name, type, and content.

    Returns:
        str: The GCS URL of the uploaded file.

    Raises:
        ValueError: If the file type is unsupported or unknown.
    """
    # Decode file content from base64 string or use bytes directly
    if isinstance(file_data.file, str):
        # If string, assume base64; strip prefix if present
        base64_str = file_data.file.split(",", 1)[-1] if file_data.file.startswith("data:") else file_data.file
        try:
            file_bytes = base64.b64decode(base64_str)
        except Exception:
            raise ValueError("Invalid base64 data.")
    elif isinstance(file_data.file, (bytes, bytearray)):
        file_bytes = file_data.file
    else:
        raise ValueError("File content must be base64 string or bytes.")

    # Determine GCS folder based on content type
    if file_data.type.startswith("image/"):
        folder = f"image/{convo_id}"
    elif file_data.type.startswith("audio/"):
        folder = f"audio/{convo_id}"
    elif file_data.type.startswith("application/") or file_data.type.startswith("text/"):
        folder = f"docs/{convo_id}"
    else:
        raise ValueError("Unsupported file type.")

    # Determine file extension from name or file content
    if hasattr(file_data, "name") and "." in file_data.name:
        extension = "." + file_data.name.split(".")[-1]
    else:
        kind = filetype.guess(file_bytes)
        extension = f".{kind.extension}" if kind else ""

    # Generate a unique filename for the uploaded file
    unique_filename = f"{folder}/{uuid.uuid4().hex}{extension}"

    # Upload file to GCS
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(file_bytes, content_type=file_data.type)

    # Return the public GCS URL of the uploaded file
    return f"https://storage.cloud.google.com/{BUCKET_NAME}/{unique_filename}"

async def delete_files_from_gcs(convo_id: str) -> None:
    """
    Deletes all files related to a conversation from Google Cloud Storage.

    Args:
        convo_id (str): The conversation ID whose files should be deleted.

    Raises:
        Exception: If an error occurs during deletion.
    """
    # Initialize GCS client and bucket
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)

    # Define folders to search for files to delete
    folders = [f"image/{convo_id}", f"audio/{convo_id}", f"docs/{convo_id}"]

    # Iterate through each folder and delete all blobs (files)
    for prefix in folders:
        blobs = list(bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
