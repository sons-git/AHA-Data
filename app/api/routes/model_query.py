from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils import build_error_response
from qdrant_client.conversions import common_types as types
from database.qdrant_client import hybrid_search_endpoint
from database.redis_client import get_redis_config

router = APIRouter(prefix="/api/model_query", tags=["Model Query"])

@router.get("/hybrid_search")
def hybrid_search(query: str = None, collection_name: str = None, limit: int = None) -> list[types.QueryResponse]:
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
        result = hybrid_search_endpoint(
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
    