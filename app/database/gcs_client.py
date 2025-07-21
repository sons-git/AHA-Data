import uuid
import base64
import filetype
from google.cloud import storage
from google.oauth2 import service_account
from app.database.redis_client import get_redis_config

# Get credentials and bucket name
gcs_key_data = get_redis_config("gcs-service-key")
credentials = service_account.Credentials.from_service_account_info(gcs_key_data)
BUCKET_NAME = get_redis_config("api_keys")["BUCKET_NAME"]

def upload_file_to_gcs(convo_id: str, files: list[bytes]) -> list[str]:
    """
    Uploads multiple files to GCS and returns their URLs.

    Args:
        convo_id (str): The conversation ID used for folder structure.
        files (list[bytes]): A list of file contents in bytes.

    Returns:
        list[str]: A list of GCS URLs of the uploaded files.

    Raises:
        ValueError: If any file has an unsupported or unknown type.
    """
    urls = []
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)

    for file_bytes in files:
        kind = filetype.guess(file_bytes)
        if kind is None:
            raise ValueError("Unsupported or unknown file type.")

        content_type = kind.mime
        extension = f".{kind.extension}"

        if content_type.startswith("image/"):
            folder = f"image/{convo_id}"
        elif content_type.startswith("audio/"):
            folder = f"audio/{convo_id}"
        elif content_type.startswith("application/"):
            folder = f"docs/{convo_id}"
        else:
            raise ValueError(f"Unsupported file type: {content_type}")

        unique_filename = f"{folder}/{uuid.uuid4().hex}{extension}"
        blob = bucket.blob(unique_filename)
        blob.upload_from_string(file_bytes, content_type=content_type)

        url = f"https://storage.cloud.google.com/{BUCKET_NAME}/{unique_filename}"
        urls.append(url)

    return urls


def delete_files_from_gcs(convo_id: str) -> None:
    """
    Deletes all files related to a conversation from GCS.

    Args:
        convo_id (str): The conversation ID whose files should be deleted.

    Raises:
        Exception: If an error occurs during deletion.
    """
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)

    folders = [f"image/{convo_id}", f"audio/{convo_id}", f"docs/{convo_id}"]

    for prefix in folders:
        blobs = list(bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
