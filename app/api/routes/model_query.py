from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.common import build_error_response
from app.database.redis_client import get_redis_config

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