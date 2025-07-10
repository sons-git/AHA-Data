import os
import uuid
import base64
import filetype
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

# Set your bucket name and credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "database/service-account-key.json"
BUCKET_NAME = os.getenv("BUCKET_NAME")

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
    try:
        # Decode base64 to bytes
        file_bytes = base64.b64decode(base64_data)
    except Exception:
        raise ValueError("Invalid base64 data.")

    # Guess MIME type and extension
    kind = filetype.guess(file_bytes)
    if kind is None:
        raise ValueError("Unsupported or unknown file type.")

    content_type = kind.mime
    extension = f".{kind.extension}"

    # Determine folder by MIME type
    if content_type.startswith("image/"):
        folder = f"image/{convo_id}"
    elif content_type.startswith("audio/"):
        folder = f"audio/{convo_id}"
    elif content_type.startswith("application/"):
        folder = f"docs/{convo_id}"
    else:
        raise ValueError("Unsupported file type.")

    # Generate unique filename
    unique_filename = f"{folder}/{uuid.uuid4().hex}{extension}"

    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(file_bytes, content_type=content_type)

    return f"https://storage.cloud.google.com/{BUCKET_NAME}/{unique_filename}?authuser=0"