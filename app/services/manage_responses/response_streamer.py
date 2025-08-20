import asyncio
import traceback
import json
import httpx
from app.database.redis_client import get_redis_config
from fastapi.encoders import jsonable_encoder
from app.database.mongo_client import save_message
from app.schemas.conversations import Message, ProcessedMessage

BACKEND_URL = get_redis_config("api_keys").get("BACKEND_URL")
    
async def stream_response(conversation_id: str, message: Message, processed_message: ProcessedMessage):
        """Stream data and get properly formatted final response"""
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=300.0) as client:
                response = await client.post(
                    "/api/conversations/stream",
                    json=jsonable_encoder(processed_message)
                )
            if response.status_code != 200:
                raise RuntimeError(f"Backend error: {response.status_code}")
                    
            model_response = response.json()
            final_response = model_response.get("response", "")

            asyncio.create_task(save_message(convo_id=conversation_id, message=message, response=final_response))

            return final_response
        
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Stream processing failed: {str(e)}")

        asyncio.create_task(save_message(convo_id=conversation_id, message=message, response=final_response))
            raise RuntimeError(f"Stream processing failed: {str(e)}")