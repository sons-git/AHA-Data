import re
import html

async def clean_text_for_speech(text: str) -> str:
    """
    Clean input text for TTS models:
    - Remove HTML tags
    - Decode HTML entities
    - Normalize whitespace
    - Remove unsupported special characters (optional)
    """
    if not text:
        return ""

    # 1. Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)

    # 2. Decode HTML entities (e.g., &amp; -> &)
    cleaned = html.unescape(cleaned)

    # 3. Remove unwanted special chars (keeping basic punctuation)
    cleaned = re.sub(r"[^a-zA-Z0-9\s.,!?;:'\"-]", "", cleaned)

    # 4. Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned