from qdrant_client import AsyncQdrantClient, models
from app.database.redis_client import get_redis_config
from app.utils.text_processing.text_embedding import embed
from qdrant_client.conversions import common_types as types

api_keys = get_redis_config("api_keys")
# Initialize Qdrant async client using environment variables
qdrant_client = AsyncQdrantClient(
    url=api_keys["QDRANT_URL"], 
    api_key=api_keys["QDRANT_API_KEY"]
)

async def hybrid_search(query: str = None, collection_name: str = None, limit: int = None) -> list[types.QueryResponse]:
    """
    Perform hybrid search using both dense and sparse vectors with Reciprocal Rank Fusion (RRF) from ranx.
    
    Args:
        query: The search query
        collection_name: Name of the Qdrant collection
        limit: Number of final results to return
    
    Returns:
        List of search results ranked by RRF score
    """
    try:
        # Generate query vectors
        embedded_query, query_indices, query_values = await embed(query)
        
        # Perform separate searches for dense and sparse vectors
        results = await qdrant_client.query_batch_points(
            collection_name=collection_name,
            requests=[
                models.QueryRequest(
                    query=embedded_query,
                    using="text-embedding",
                    limit=limit, 
                    with_payload=True
                ),
                models.QueryRequest(
                    query=models.SparseVector(
                        indices=query_indices,
                        values=query_values,
                    ),
                    limit=limit, 
                    with_payload=True,
                    using="sparse-embedding"
                ),
            ],
        )
        return results
    except Exception as e:
        print(f"[Qdrant] Error performing hybrid search: {e}")