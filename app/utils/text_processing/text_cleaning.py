import re
import html

MAX_CHARS = 100_000 

async def clean_text_for_speech(text: str) -> str:
    """
    Clean input text for TTS models:
    - Remove HTML tags
    - Decode HTML entities
    - Normalize whitespace
    - Remove unsupported special characters (optional)
    Args:
        text (str): The input text to clean.

    Returns:
        str: The cleaned text.
    """
    if not text:
        return ""

    # 1. Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)

    # 2. Decode HTML entities (e.g., &amp; -> &)
    cleaned = html.unescape(cleaned)

    # 3. Remove unwanted special chars (keeping basic punctuation)
    cleaned = re.sub(r"[^\w\s.,!?;:'\"-]", "", cleaned)

    # 4. Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned

async def clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace, removing noise, and fixing encoding issues."""
    if not text:
        return ""

    # Replace multiple spaces/tabs with a single space
    text = re.sub(r"[ \t]+", " ", text)

    # Replace multiple newlines with a single newline
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Remove non-printable/control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    # Normalize dashes/quotes
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")

    # Crop if text exceeds LLM safe limit
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n...[TRUNCATED]..."

    return text.strip()