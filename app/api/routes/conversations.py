import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.schemas.conversations import (
    Message, 
    Conversation,
    UpdateConversationRequest
)
from app.database.mongo_client import (
    create_conversation, get_all_conversations,
    get_conversation_by_id, delete_conversation_by_id, 
    update_conversation_title, save_message
)
from app.database.gcs_client import upload_file_to_gcs
from app.utils.common import build_error_response

# Create a router with a common prefix and tag for all conversation-related endpoints
router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

# Endpoint to create a new conversation for a given user
@router.post("/create/{user_id}", response_model=Conversation)
async def create_conversation_by_user_id(user_id: str, request: Request):
    """
    Create a new conversation for a given user.

    Args:
        user_id (str): The ID of the user.
        message (Message): The initial message to generate a conversation title.

    Returns:
        Conversation: The newly created conversation with a generated title.
    """
    try:
        if not user_id:
            return build_error_response("INVALID_INPUT", "User ID is required", 400)

        body = await request.json()

        async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
            title_response = await client.post(
                f"/api/conversations/generate_title/{user_id}",
                json=body,
                timeout=30.0
            )

            if title_response.status_code != 200:
                return build_error_response(
                    "TITLE_GENERATION_FAILED",
                    f"Failed to generate title: {title_response.text}",
                    500
                )

            title = title_response.json().get("title")

        result = create_conversation(user_id=user_id, title=title)

        if isinstance(result, JSONResponse):
            return result

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return build_error_response(
            "CONVERSATION_CREATION_FAILED",
            f"Failed to create conversation: {str(e)}",
            500
        )

# Endpoint to retrieve all conversations stored in the database
@router.get("/user/{user_id}", response_model=list[Conversation])
def get_all_conversations_by_user_id(user_id: str):
    """
    Retrieve all conversations belonging to a specific user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        list[Conversation]: A list of the user's stored conversations.
    """
    try:
        if not user_id:
            return build_error_response(
                "INVALID_INPUT",
                "User ID is required",
                400
            )
        
        conversations = get_all_conversations(user_id)
        
        # Check if result is an error response
        if isinstance(conversations, JSONResponse):
            return conversations
        
        return conversations
        
    except Exception as e:
        return build_error_response(
            "CONVERSATIONS_RETRIEVAL_FAILED",
            f"Failed to retrieve conversations: {str(e)}",
            500
        )


# Endpoint to retrieve a specific conversation by its ID
@router.get("/chat/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str):
    """
    Retrieve a conversation by its unique conversation ID.

    Args:
        conversation_id (str): The ID of the conversation.

    Returns:
        Conversation: The conversation object matching the given ID.
    """
    try:
        if not conversation_id:
            return build_error_response(
                "INVALID_INPUT",
                "Conversation ID is required",
                400
            )
        
        convo = get_conversation_by_id(conversation_id)
        
        # Check if result is an error response
        if isinstance(convo, JSONResponse):
            return convo
        
        if not convo:
            return build_error_response(
                "CONVERSATION_NOT_FOUND",
                "Conversation not found",
                404
            )
        
        return convo
        
    except Exception as e:
        return build_error_response(
            "CONVERSATION_RETRIEVAL_FAILED",
            f"Failed to retrieve conversation: {str(e)}",
            500
        )


@router.delete("/{conversation_id}/user/{user_id}")
async def delete_conversation(conversation_id: str, user_id: str):
    """
    Delete a specific conversation by its ID for a given user.

    Args:
        conversation_id (str): The ID of the conversation to delete.
        user_id (str): The ID of the user who owns the conversation.

    Returns:
        JSONResponse: A success message or error details.
    """
    try:
        if not conversation_id or not user_id:
            return build_error_response(
                "INVALID_INPUT",
                "Conversation ID and user ID are required",
                400
            )
        
        result = await delete_conversation_by_id(conversation_id, user_id)
        
        # Check if result is an error response
        if isinstance(result, JSONResponse):
            return result
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        return build_error_response(
            "CONVERSATION_DELETION_FAILED",
            f"Failed to delete conversation: {str(e)}",
            500
        )


# Endpoint to update conversation title (rename)
@router.put("/{conversation_id}/rename", response_model=Conversation)
async def rename_conversation(conversation_id: str, request: UpdateConversationRequest):
    """
    Rename a conversation by updating its title.

    Args:
        conversation_id (str): The ID of the conversation to rename.
        request (UpdateConversationRequest): The request containing the new title.

    Returns:
        Conversation: The updated conversation with the new title.
    """
    try:
        if not conversation_id:
            return build_error_response(
                "INVALID_INPUT",
                "Conversation ID is required",
                400
            )
        
        if not request or not request.title:
            return build_error_response(
                "INVALID_INPUT",
                "New title is required",
                400
            )
        
        updated_convo = update_conversation_title(conversation_id, request.title)
        
        # Check if result is an error response
        if isinstance(updated_convo, JSONResponse):
            return updated_convo
        
        if not updated_convo:
            return build_error_response(
                "CONVERSATION_NOT_FOUND",
                "Conversation not found or could not be updated",
                404
            )
        
        return updated_convo
        
    except Exception as e:
        return build_error_response(
            "CONVERSATION_UPDATE_FAILED",
            f"Failed to update conversation: {str(e)}",
            500
        )

@router.post("/{conversation_id}/add_message")
async def add_message(
    conversation_id: str, 
    request: Request
):
    """
    Add a user message and corresponding assistant response to a conversation.
    """
    try:
        body = await request.json()
        response = body.get("response")
        
        if not response:
            return build_error_response(
                "INVALID_INPUT",
                "Response are required",
                400
            )
        
        # Create Message object from the data
        message = Message(
            content=body.get("content"),
            image=body.get("image"),
            timestamp=body.get("timestamp")
        )
        
        if not conversation_id or not message or not response:
            return build_error_response(
                "INVALID_INPUT",
                "Conversation ID, message, and response are required",
                400
            )
        
        await save_message(conversation_id, message, response)
      
    except Exception as e:
        return build_error_response(
            "MESSAGE_SAVE_FAILED",
            f"Failed to save message: {str(e)}",
            500
        )