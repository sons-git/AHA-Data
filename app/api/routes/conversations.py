import httpx
import traceback
from typing import List
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse

from app.database.mongo_client import (
    create_conversation,
    get_all_conversations,
    get_conversation_by_id,
    delete_conversation_by_id,
    update_conversation_title,
    save_message,
)
from app.schemas.conversations import (
    FileData,
    Message,
    Conversation,
    UpdateConversationRequest,
)
from app.utils.file_processing import handle_file_processing
from app.utils.common import build_error_response, classify_message

base_url = "http://localhost:8001"

# Create a router with a common prefix and tag for all conversation-related endpoints
router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.post("/create/{user_id}", response_model=Conversation)
async def create_conversation_by_user_id(
    user_id: str, 
    content: str = Form(None),
    files: List[UploadFile] = File(default=[])
    ):

    """
    Create a new conversation for a given user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        Conversation: The newly created conversation with a generated title.
    """
    try:
        if not user_id:
            return build_error_response("INVALID_INPUT", "User ID is required", 400)

        # Convert UploadFile to FileData
        file_data_list = []
        for upload in files:
            file_bytes = await upload.read()
            file_data_list.append(FileData(
                name=upload.filename,
                type=upload.content_type,
                file=file_bytes
            ))

        # Process files and generate conversation title
        processed_file = await handle_file_processing(content, file_data_list)
        processed_message = jsonable_encoder(processed_file)

        async with httpx.AsyncClient(base_url=base_url) as client:
            title_response = await client.post(
                "/api/conversations/generate_title",
                json=processed_message,
                timeout=60.0
            )

            if title_response.status_code != 200:
                return build_error_response(
                    "TITLE_GENERATION_FAILED",
                    f"Failed to generate title: {title_response.text}",
                    500
                )

            title = title_response.json().get("title")

        result = await create_conversation(user_id=user_id, title=title)

        if isinstance(result, JSONResponse):
            return result

        return result

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            "CONVERSATION_CREATION_FAILED",
            f"Failed to create conversation: {str(e)}",
            500
        )


@router.get("/user/{user_id}", response_model=list[Conversation])
async def get_all_conversations_by_user_id(user_id: str):
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

        conversations = await get_all_conversations(user_id)

        if isinstance(conversations, JSONResponse):
            return conversations

        return conversations

    except Exception as e:
        return build_error_response(
            "CONVERSATIONS_RETRIEVAL_FAILED",
            f"Failed to retrieve conversations: {str(e)}",
            500
        )


@router.get("/chat/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
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

        convo = await get_conversation_by_id(conversation_id)

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

        updated_convo = await update_conversation_title(conversation_id, request.title)

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


@router.post("/{conversation_id}/{user_id}/stream")
async def stream_message(conversation_id: str,
    user_id: str,
    content: str = Form(None),
    timestamp: str = Form(None),
    files: List[UploadFile] = File(default=[])):
    """
    Stream a response to a user's message (text, image, or both) and update the conversation.

    Args:
        conversation_id (str): The ID of the conversation to append the response to.
        user_id (str): The ID of the user sending the message.

    Returns:
        StreamingResponse: A streamed response via Server-Sent Events (SSE).
    """
    try:
        # Convert UploadFile to FileData
        file_data_list = []
        for upload in files:
            file_bytes = await upload.read()
            file_data_list.append(FileData(
                name=upload.filename,
                type=upload.content_type,
                file=file_bytes
            ))

        message = Message(
            content=content,
            files=file_data_list,
            timestamp=timestamp
        )
        
        if not conversation_id or not user_id:
            return build_error_response(
                "INVALID_INPUT",
                "Conversation ID and user ID are required",
                400
            )

        if not message:
            return build_error_response(
                "INVALID_INPUT",
                "Message is required",
                400
            )

        if not message.content and not getattr(message, "files", None):
            return build_error_response(
                "INVALID_INPUT",
                "Message must contain either text content or files",
                400
            )

        # Process files and classify message
        processed_file = await handle_file_processing(message.content, message.files)
        classified_message = await classify_message(processed_file, conversation_id)
        processed_message = jsonable_encoder(classified_message)
        async def event_generator():
            """
            Generator function to stream data as Server-Sent Events (SSE).
            """
            final_response = ""
            async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
                async with client.stream("POST", "/api/conversations/stream", json=processed_message, timeout=60.0) as response:
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line.removeprefix("data: ").strip()
                        if data == "[DONE]":
                            break
                        final_response += data + " "
                        yield f"data: {data}\n\n"

            # Save full response once stream finishes
            await save_message(convo_id=conversation_id, message=message, response=final_response)
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            "STREAM_INITIALIZATION_FAILED",
            f"Failed to initialize message stream: {str(e)}",
            500
        )