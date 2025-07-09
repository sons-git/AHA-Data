import os
import uuid
import filetype
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

# Set your bucket name and credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "database/service-account-key.json"
BUCKET_NAME = os.getenv("BUCKET_NAME")

def upload_file_to_gcs(user_id: str, file_bytes: bytes) -> str:
    """
    Uploads file to appropriate folder in GCS and returns its GCS URL.
    
    Args:
        file_bytes (bytes): The content of the file to upload.
        user_id (str): The ID of the user uploading the file.
    Returns:
        str: The GCS URL of the uploaded file.
    Raises:
        ValueError: If the file type is unsupported or unknown.
    """

    # Infer content type and extension
    kind = filetype.guess(file_bytes)
    if kind is None:
        raise ValueError("Unsupported or unknown file type.")

    content_type = kind.mime
    extension = f".{kind.extension}"  

    # Determine folder based on MIME type
    if content_type.startswith("image/"):
        folder = f"image/{user_id}"
    elif content_type.startswith("audio/"):
        folder = f"audio/{user_id}"
    elif content_type.startswith("application/"):
        folder = f"docs/{user_id}"
    else:
        raise ValueError("Unsupported file type.")

    # Create unique filename
    unique_filename = f"{folder}/{uuid.uuid4().hex}{extension}"

    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(file_bytes, content_type=content_type)

    # Return GCS URL (accessible if user has permission)
    return f"https://storage.cloud.google.com/{BUCKET_NAME}/{unique_filename}?authuser=0"



