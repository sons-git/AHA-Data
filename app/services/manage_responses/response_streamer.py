import json
import httpx
from fastapi.encoders import jsonable_encoder
from app.database.mongo_client import save_message
from app.schemas.conversations import Message, ProcessedMessage


base_url = "http://localhost:8001"
    
async def stream_response(conversation_id: str, message: Message, processed_message: ProcessedMessage):
        """Stream data and get properly formatted final response"""
        final_response = ""
        
        async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
            async with client.stream("POST", "/api/conversations/stream", json=jsonable_encoder(processed_message), timeout=300.0) as response:
                if response.status_code != 200:
                    yield f"data: ERROR - Backend error: {response.status_code}\n\n"
                    return
                    
                async for line in response.aiter_lines():
                    if line.strip() and line.startswith('data: '):
                        try:
                            chunk_data = json.loads(line[6:])
                            
                            if chunk_data["type"] == "chunk":
                                yield f"data: {chunk_data['data']}\n\n"
                            elif chunk_data["type"] == "done":
                                final_response = chunk_data["full_response"]
                                break 
                            elif chunk_data["type"] == "error":
                                yield f"data: ERROR - {chunk_data['data']}\n\n"
                                return
                                
                        except json.JSONDecodeError:
                            yield f"data: ERROR - Invalid JSON from backend\n\n"
                            return

        await save_message(convo_id=conversation_id, message=message, response=final_response)
        yield "data: [DONE]\n\n"