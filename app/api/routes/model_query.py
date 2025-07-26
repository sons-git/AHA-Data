from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx
from app.utils.common import build_error_response
from app.database.redis_client import get_redis_config
from qdrant_client.conversions import common_types as types

router = APIRouter(prefix="/api/model_query", tags=["Model Query"])
   
@router.get("/get_config")
def get_config(name: str) -> dict:
    """
    Retrieve a configuration from Redis by name.
    
    Args:
        name: The name of the configuration to retrieve.
        
    Returns:
        The configuration as a dictionary.
        
    Raises:
        HTTPException: If the configuration is not found or cannot be parsed.
    """
    try:
        if not name:
            return build_error_response(
                "INVALID_NAME",
                "Configuration name is required.",
                400
            )
        
        config = get_redis_config(name)
        # Check if result is an error response
        if isinstance(config, JSONResponse):
            return config
        
        if not config:
            return build_error_response(
                "CONFIG_NOT_FOUND",
                f"Config '{name}' not found in Redis.",
                404
            )
        
        return config
    
    except Exception as e:
        return build_error_response(
            "CONFIG_RETRIEVAL_FAILED",
            f"Failed to retrieve config '{name}': {str(e)}",
            500
        )

# async def call_add_message_endpoint(conversation_id: str, message: Message, response: str):
#     """
#     Call the add_message endpoint via HTTP request.
#     """
#     try:
#         base_url = DATA_URL
        
#         # Serialize the image if it exists
#         serialized_image = serialize_image(message.image)
        
#         async with httpx.AsyncClient() as client:
#             response_data = await client.post(
#                 f"{base_url}/api/conversations/{conversation_id}/add_message",
#                 json={
#                     "content": message.content,
#                     "image": serialized_image,
#                     "timestamp": message.timestamp.isoformat(),
#                     "response": response
#                 },
#                 timeout=30.0
#             )
            
#             if response_data.status_code != 200:
#                 print(f"Failed to add message: {response_data.status_code} - {response_data.text}")
                
#     except Exception as e:
#         print(f"Error calling add_message endpoint: {str(e)}")