import time
import asyncio
import dspy
from datetime import datetime
from googletrans import Translator
from fastapi.responses import JSONResponse
from app.database.qdrant_client import hybrid_search
from app.schemas.conversations import ProcessedMessage
from app.services.manage_models.model_manager import model_manager
from app.utils.text_processing.reciprocal_rank_fusion import rrf

# Helper function to build a standardized JSON error response
def build_error_response(code: str, message: str, status: int) -> JSONResponse:
    """
    Construct a standardized JSON error response for API endpoints.

    Args:
        code (str): A short error code identifier (e.g., "RESOURCE_NOT_FOUND").
        message (str): A human-readable error message.
        status (int): HTTP status code (e.g., 400, 404, 500).

    Returns:
        JSONResponse: A FastAPI JSONResponse object containing the formatted error.
    """
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "status": status,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )

# Convert MongoDB document (_id) into a serializable dictionary
def serialize_mongo_document(doc):
    """
    Convert a MongoDB document into a serializable dictionary for API responses.

    Args:
        doc (dict): A MongoDB document.

    Returns:
        dict | None: A sanitized and serializable dictionary, or None if the input is falsy.
    """
    if not doc:
        return None

    doc = doc.copy()
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

# Convert a MongoDB user document into a serializable API format
def serialize_user(user):
    """
    Convert a MongoDB user document into a serializable API format.

    Args:
        user (dict): Raw MongoDB user document.

    Returns:
        dict | None: Cleaned user data including `id`, `fullName`, `email`, and `phone`.
    """
    if not user:
        return None
    return {
        "id": str(user.get("_id", "")),
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", "")
    }

# Log the time taken to execute a process
def log_execution_time(start_time: float = None, process_name: str = None) -> None:
    """
    Log the time taken to execute a process.

    Args:
        start_time (float): The timestamp when the process started.
        process_name (str): A descriptive name of the process (e.g., "LLM", "RAG").

    Returns:
        None
    """
    execution_time = time.time() - start_time
    color = "[green]" if process_name and ("RAG" in process_name or "Dynamic" in process_name) else ""
    end_color = "[/green]" if color else ""
    print(f"{process_name} inference took {color}{execution_time:.2f} seconds{end_color}")

async def get_classifier() -> dspy.Module:
    """
    Load and return the classifier model from the model manager.
    Returns:
        dspy.Module: The classifier module for zero-shot classification.
    Raises:
        Exception: If the classifier model cannot be loaded.
    """
    try:
        classifier = model_manager.get_model("classifier")
        return classifier
    except Exception as e:
        print(f"Failed to load classifier: {str(e)}")
        raise Exception(f"Classifier loading failed: {str(e)}")
    
# Async function to classify text
async def classify_text(processed_message: ProcessedMessage = None) -> str:
    """
    Translate and classify the user's text input in parallel to determine if it's medical-related or not.

    Args:
        processed_message (ProcessedMessage): The user message containing text.

    Returns:
        str: The classification result, typically 'medical-related' or 'not-medical-related'.

    Raises:
        Exception: If translation, classification, or either task fails.
    """
    try:
        async with Translator() as translator:
            translate_task = translator.translate(
                text=processed_message.content, src="auto", dest="en"
            )
            classifier_task = get_classifier()
            start_time = time.time()
            translated_prompt, classifier = await asyncio.gather(
                translate_task, classifier_task
            )
        text_result = await classifier.classify_text(
            prompt=translated_prompt.text[:100]
        )
        log_execution_time(start_time, "Text Classification")
        return text_result
    except Exception as e:
        print(f"Text classification failed: {str(e)}")
        raise Exception(f"Text classification failed: {str(e)}")

# Async function to fetch recent conversations and points
async def classify_message(processed_message: ProcessedMessage, convo_id: str) -> ProcessedMessage:
    """
    Fetch recent conversations and points concurrently, then update the processed_message context.

    Args:
        processed_message: The message object to update.
        convo_id: The conversation ID to fetch recent messages from.

    Returns:
        ProcessedMessage: Updates processed_message in place.
    """
    from app.database.mongo_client import get_recent_conversations
    
    # Start both operations concurrently
    text_task = asyncio.create_task(classify_text(processed_message=processed_message))
    recent_convos_task = asyncio.create_task(get_recent_conversations(convo_id=convo_id, limit=50))
    
    # Wait for text classification first (needed to determine if medical)
    text_result = await text_task
    is_medical = text_result != "not related to medical" and text_result != "code"
    
    # If medical, start hybrid search while waiting for recent conversations
    if is_medical:
        hybrid_search_task = asyncio.create_task(hybrid_search(
            query=processed_message.content,
            collection_name=text_result,
            limit=4
        ))
        
        # Wait for both remaining operations
        recent_conversations, points = await asyncio.gather(
            recent_convos_task,
            hybrid_search_task
        )
        
        processed_message.context = rrf(points=points, n_points=3, payload=["text"])
    else:
        # Just wait for recent conversations
        recent_conversations = await recent_convos_task
    
    # Update recent conversations
    processed_message.recent_conversations = recent_conversations
    
    return processed_message
