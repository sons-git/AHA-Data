from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.common import build_error_response
from app.database.redis_client import get_redis_config
from qdrant_client.conversions import common_types as types
from app.database.qdrant_client import hybrid_search_endpoint, get_recent_conversations

router = APIRouter(prefix="/api/model_query", tags=["Model Query"])

@router.get("/hybrid_search")
async def hybrid_search(query: str = None, collection_name: str = None, limit: int = None) -> list[types.QueryResponse]:
    """
    Perform a hybrid search using both dense and sparse vectors with Reciprocal Rank Fusion (RRF).
    Args:
        query: The search query string.
        collection_name: The name of the collection to search in.
        limit: The maximum number of results to return.     
    Returns:
        A list of search results, or an error response if the search fails.
    Raises:
        HTTPException: If the query, collection name, or limit is invalid or if the search fails.
    """
    try:        
        if not query or not collection_name or not limit:
            return build_error_response(
                "INVALID_QUERY",
                "Query parameter, Collection name and Limit parameter are required.",
                400
            )
        
        # Perform the hybrid search
        result = await hybrid_search_endpoint(
            query=query,
            collection_name=collection_name,
            limit=limit
        )
        
        # Check if result is an error response
        if isinstance(result, JSONResponse):
            return result
        
        return result
    
    except Exception as e:
        return build_error_response(
            "HYBRID_SEARCH_FAILED",
            f"Failed to perform hybrid search: {str(e)}",
            500
        )
        
@router.get("/recent_conversations")
async def recent_conversations(
    collection_name: str,
    limit: int
):
    """
    Retrieve the most recent conversations from the specified Qdrant collection.

    Args:
        collection_name: Name of the Qdrant collection.
        limit: Number of recent conversations to retrieve (default: 50).

    Returns:
        JSON response with the formatted conversation string.
    """
    try:
        result = await get_recent_conversations(collection_name=collection_name, limit=limit)
        return JSONResponse(content={"recent_conversations": result}, status_code=200)
    
    except Exception as e:
        print(f"[API Error] Failed to fetch recent conversations: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to retrieve recent conversations"}
        )
   
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
    