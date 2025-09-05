import asyncio
import csv
import io
import base64
import docx2txt
from typing import List, Tuple, Optional
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.pdfdocument import PDFEncryptionError

import dspy
from app.schemas.conversations import FileData, ProcessedMessage
from app.utils.image_processing import convert_to_dspy_image
from app.utils.text_processing.text_cleaning import clean_text
from .audio_processing import process_filedata_with_diarization

async def extract_text_from_file(file_data: FileData) -> Optional[str]:
    """
    Extract text content from various file types based on FileData.file.

    Args:
        file_data (FileData): Metadata and content of the file.

    Returns:
        Optional[str]: Extracted text content, or None if extraction fails.
    """
    try:
        # Decode bytes from base64 if needed
        if isinstance(file_data.file, str):
            content_bytes = base64.b64decode(file_data.file.split(",", 1)[-1])
        else:
            content_bytes = file_data.file

        # Handle plain text and markdown files
        if file_data.type in {"text/plain", "text/markdown"}:
            text = content_bytes.decode("utf-8", errors="ignore")
            return await clean_text(text)

        # Handle CSV files
        elif file_data.type == "text/csv":
            decoded = content_bytes.decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(decoded))
            rows = [" | ".join(row) for row in reader]
            text = "\n".join(rows) if rows else ""
            return await clean_text(text)

        # Handle PDF files
        elif file_data.type == "application/pdf":
            if file_data.type == "application/pdf":
                try:
                    text = extract_text(io.BytesIO(content_bytes))
                    if not text:  # pdfminer returns None if nothing could be extracted
                        return f"PDF file '{file_data.name}' might be encrypted or empty."
                    return await clean_text(text) if text else text
                except PDFEncryptionError:
                    return f"PDF file '{file_data.name}' is encrypted and cannot be processed."
                except PDFSyntaxError as e:
                    return f"Corrupted or unreadable PDF '{file_data.name}': {e}"
                except Exception as e:
                    return f"Error processing PDF '{file_data.name}': {e}"

        # Handle DOCX files
        elif file_data.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            try:
                text = docx2txt.process(io.BytesIO(content_bytes))
                if text and text.strip():
                    return await clean_text(text)
                else:
                    return f"DOCX file '{file_data.name}' is empty or unreadable."
            except Exception as e:
                return f"Error processing DOCX '{file_data.name}': {e}"

    except Exception as e:
        return (f"Failed to extract text from {file_data.name}: {e}")

async def classify_file(files: List[FileData]) -> Tuple[List[FileData], List[FileData], List[FileData]]:
    """
    Classify files into images and documents based on their MIME types.

    Args:
        files (List[FileData]): List of FileData objects to classify.

    Returns:
        Tuple[List[FileData], List[FileData]]: Two lists - one for image files, one for document files.
    """
    # Separate image files and document files by MIME type
    image_files = [f for f in files if f.type.startswith("image/")]
    doc_files = [f for f in files if f.type.startswith(("text/", "application/"))]
    audio_files = [f for f in files if f.type.startswith("audio/")]
    return image_files, doc_files, audio_files

async def extract_text_concurrent(files: List[FileData]) -> List[str]:
    """
    Extract text from multiple files concurrently.
    Args:
        files (List[FileData]): List of FileData objects containing file data.
    Returns:
        List[str]: List of extracted text strings from the provided files.
    Raises:
        Exception: If any file extraction fails.
    """
    tasks = [extract_text_from_file(file_data) for file_data in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    extracted = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"Failed to extract text from file at index {idx}: {r}")
        elif isinstance(r, str) and r.strip():
            extracted.append(r)
    return extracted

async def convert_images_concurrent(files: List[FileData]) -> List[dspy.Image]:
    """
    Convert image files to dspy.Image objects concurrently. 
    Args:
        files (List[FileData]): List of FileData objects containing image data.
    Returns:
        List[dspy.Image]: List of dspy.Image objects created from the provided files.
    Raises:
        Exception: If any file conversion fails.
    """
    tasks = []
    for file_data in files:
        try:
            if isinstance(file_data.file, (bytes, bytearray)):
                base64_data = base64.b64encode(file_data.file).decode("utf-8")
                tasks.append(convert_to_dspy_image(base64_data))
        except Exception as e:
            print(f"Failed to prepare image {file_data.name}: {e}")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    images = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"Failed to convert image file at index {idx}: {r}")
        else:
            images.append(r)
    return images

async def handle_file_processing(content: str, files: List[FileData]) -> ProcessedMessage:
    """
    Process provided files, extract text, and return combined content with dspy.Image objects.

    Args:
        content (str): Additional content provided by the user.
        files (List[FileData]): List of FileData objects (already base64 or bytes).

    Returns:
        ProcessedMessage: Combined text content and list of dspy.Image objects.
    """
    if isinstance(content, str) and content.strip() == "":
        content = None
    
    if not files:
        return ProcessedMessage(
            content=content,
            images=None,
            context=None,
            recent_conversations=None,
            files=None,
            audio=None
        )
    
    extracted_texts = []
    dspy_images = []
    extracted_audio = []

    # Classify files into images and documents
    image_files, doc_files, audio_files = await classify_file(files)
    
    extracted_texts, dspy_images, extracted_audio = await asyncio.gather(
        extract_text_concurrent(doc_files),
        convert_images_concurrent(image_files),
        asyncio.gather(*[asyncio.to_thread(process_filedata_with_diarization, f) for f in audio_files])
    )

    return ProcessedMessage(
        content=content,
        images=dspy_images,
        context=None,
        recent_conversations=None,
        files=extracted_texts,
        audio=extracted_audio
    )
