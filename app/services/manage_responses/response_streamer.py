from fastapi.encoders import jsonable_encoder
import httpx
from app.database.mongo_client import save_message
from app.schemas.conversations import Message, ProcessedMessage


base_url = "http://localhost:8001"

async def stream_response(conversation_id: str, message: Message, processed_message: ProcessedMessage):
    """
    Generator function to stream data as Server-Sent Events (SSE).
    """
    final_response = ""
    json_message = jsonable_encoder(processed_message)
    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        async with client.stream("POST", "/api/conversations/stream", json=json_message, timeout=30.0) as response:
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