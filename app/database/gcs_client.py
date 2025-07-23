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

def upload_file_to_gcs(convo_id: str, base64_data: str) -> str:
    """
    Uploads a base64-encoded file to GCS and returns its GCS URL.

    Args:
        convo_id (str): The conversation ID used for folder structure.
        base64_data (str): The base64-encoded content of the file.

    Returns:
        str: The GCS URL of the uploaded file.

    Raises:
        ValueError: If the file type is unsupported or unknown.
    """
   # Remove prefix if present: "data:<mime>;base64,"
    if base64_data.startswith("data:"):
        header, base64_str = base64_data.split(",", 1)
    else:
        base64_str = base64_data

    try:
        file_bytes = base64.b64decode(base64_str)
    except Exception:
        raise ValueError("Invalid base64 data.")

    kind = filetype.guess(file_bytes)
    if kind is None:
        raise ValueError("Unsupported or unknown file type.")

    content_type = kind.mime
    extension = f".{kind.extension}"

    # Determine folder based on content type
    if content_type.startswith("image/"):
        folder = f"image/{convo_id}"
    elif content_type.startswith("audio/"):
        folder = f"audio/{convo_id}"
    elif content_type.startswith("application/"):
        folder = f"docs/{convo_id}"
    else:
        raise ValueError("Unsupported file type.")

    unique_filename = f"{folder}/{uuid.uuid4().hex}{extension}"

    # Upload to GCS
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(file_bytes, content_type=content_type)

    return f"https://storage.cloud.google.com/{BUCKET_NAME}/{unique_filename}"


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
