from uuid import uuid4
from typing import List
from app.utils.common import build_error_response
from qdrant_client import AsyncQdrantClient, models
from app.database.redis_client import get_redis_config
from app.utils.text_processing.text_embedding import embed
from qdrant_client.conversions import common_types as types
from qdrant_client.models import PointStruct, ScoredPoint, PointIdsList

api_keys = get_redis_config("api_keys")
# Initialize Qdrant async client using environment variables
qdrant_client = AsyncQdrantClient(
    url=api_keys["QDRANT_URL"], 
    api_key=api_keys["QDRANT_API_KEY"]
)

async def get_all_messages(collection_name: str) -> List[ScoredPoint]:
    """
    Retrieve all messages for a user from the Qdrant collection.

    Args:
        collection_name: Name of the Qdrant collection

    Returns:
        List of ScoredPoint objects for the user
    """
    try:
        scrolled_points, _ = await qdrant_client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True
        )
        return scrolled_points
    except Exception as e:
        print(f"[Qdrant] Error fetching messages for user {collection_name}: {e}")
        return []

async def remove_oldest_message(existing_messages: list, collection_name: str):
    """
    Remove the oldest message based on timestamp from a specific Qdrant collection.
    Args:
        existing_messages: List of message points
        collection_name: Name of the Qdrant collection
    """
    if not existing_messages:
        return
    try:
        # Sort messages by timestamp and select the oldest
        oldest = sorted(existing_messages, key=lambda p: p.payload["timestamp"])[0]
        await qdrant_client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=[oldest.id])
        )
    except Exception as e:
        print(f"[Qdrant] Error removing oldest message from {collection_name}: {e}")

async def ensure_collection_exists(collection_name: str):
    """
    Ensure the Qdrant collection exists, create it if not.
    Args:
        collection_name: Name of the Qdrant collection based on user ID
    """
    try:
        if not await qdrant_client.collection_exists(collection_name=collection_name):
            await qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "text-embedding": models.VectorParams(size=384, distance=models.Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse-embedding": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                },
            )
    except Exception as e:
        print(f"Error: {e}")

async def add_message_vector(collection_name: str, conversation_id: str, user_message: str, bot_response: str, timestamp: str) -> None:
    """
    Embed the user message and insert it into Qdrant.
    If more than 50 messages exist for the user, remove the oldest one first.
    Args:
        collection_name: Name of the Qdrant collection
        conversation_id: The conversation's unique identifier
        user_message: The user's message text
        bot_response: The assistant's reply
        timestamp: Timestamp of the message
    """
    try:
        # Ensure the collection exists
        await ensure_collection_exists(collection_name)

        # Retrieve existing messages for the user
        existing_messages = await get_all_messages(collection_name)

        # Maintain rolling window of 50 messages per user
        if len(existing_messages) >= 50:
            await remove_oldest_message(existing_messages, collection_name)

        # Generate dense and sparse embeddings for the message
        dense_vector, sparse_indices, sparse_values = await embed(user_message)

        # Upsert the message and its embeddings into Qdrant
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector={
                        "text-embedding": dense_vector,
                        "sparse-embedding": models.SparseVector(
                            indices=sparse_indices,
                            values=sparse_values
                        )
                    },
                    payload={
                        "conversation_id": conversation_id,
                        "timestamp": timestamp,
                        "user_message": user_message,
                        "bot_response": bot_response
                    }
                )
            ]
        )
    except Exception as e:
        print(f"[Qdrant] Error adding message to vector DB: {e}")

async def delete_conversation_vectors(collection_name: str, conversation_id: str):
    """
    Delete all vector points in a Qdrant collection associated with a specific conversation ID.

    This function retrieves up to 10,000 points from the specified Qdrant collection,
    filters them locally by `conversation_id` in the payload, and deletes matching vectors.

    Args:
        collection_name (str): The name of the Qdrant collection to search.
        conversation_id (str): The conversation ID used to identify which vectors to delete.

    Logs:
        - Number of points deleted.
        - Any errors encountered during the process.

    Raises:
        Exception: If any error occurs during the scroll or delete operations.
    """
    try:
        # Get ALL points (no filter to avoid index requirement)
        scrolled_points, _ = await qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        
        # Filter in Python to find matching conversation_id
        matching_point_ids = [
            point.id for point in scrolled_points 
            if point.payload and point.payload.get("conversation_id") == conversation_id
        ]
        
        # Delete by IDs if any found
        if matching_point_ids:
            await qdrant_client.delete(
                collection_name=collection_name,
                points_selector=matching_point_ids,
                wait=True
            )
            
        print(f"Deleted {len(matching_point_ids)} points for conversation {conversation_id}")
        
    except Exception as e:
        print(f"[Qdrant] Error deleting conversation vectors: {e}")
        raise

async def get_recent_conversations(collection_name: str, limit: int) -> str:
    """
    Retrieve the most recent conversations from the Qdrant collection based on timestamp.

    Args:
        collection_name: Name of the Qdrant collection
        limit: Number of recent conversations to retrieve (default: 50)

    Returns:
        Formatted string with timestamp, user_message, and bot_response for each conversation
    """
    try:
        # Get all points first
        scrolled_points, _ = await qdrant_client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True
        )
        if scrolled_points:
            # Sort by timestamp (newest first) and take the specified limit
            sorted_conversations = sorted(
                scrolled_points,
                key=lambda x: x.payload.get('timestamp', ''),
                reverse=False
            )
            
            recent_conversations = sorted_conversations
            
            # Format conversations as string
            context_chunks = []
            payload_keys = ['user_message', 'bot_response']
            
            for idx, doc in enumerate(recent_conversations):
                payload_content = [f"{key}: {doc.payload.get(key, '')}" for key in payload_keys]
                content = f"Conversation {idx}:\n" + "\n".join(payload_content)
                context_chunks.append(content)

            
            separator = "\n\n------------------------------------------------------------\n\n"
            return f"Recent conversations:\n{separator.join(context_chunks)}"
        else:
            return "This is user's first ever message"
        
    except Exception as e:
        print(f"[Qdrant] Error fetching recent conversations for collection {collection_name}: {e}")
        return ""

async def hybrid_search_endpoint(query: str = None, collection_name: str = None, limit: int = None) -> list[types.QueryResponse]:
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
        return build_error_response(
            "HYBRID_SEARCH_BACKEND_ERROR",
            f"Failed to search Qdrant: {str(e)}",
            500
        )