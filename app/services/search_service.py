from algoliasearch.search.client import SearchClient

from app.database.redis_client import get_redis_config

ALGOLIA_APP_ID = get_redis_config("api_keys")["ALGOLIA_APP_ID"]
ALGOLIA_SEARCH_API_KEY = get_redis_config("api_keys")["ALGOLIA_SEARCH_API_KEY"]
ALGOLIA_WRITE_API_KEY = get_redis_config("api_keys")["ALGOLIA_WRITE_API_KEY"]
INDEX_NAME = "conversations"

search_client = SearchClient(ALGOLIA_APP_ID, ALGOLIA_SEARCH_API_KEY)
write_client = SearchClient(ALGOLIA_APP_ID, ALGOLIA_WRITE_API_KEY)

async def search_conversations_by_user_id(query: str, user_id: str):
    """
    Search conversations by user ID and sender using Algolia.
    Args:
        query (str): The search query.
        user_id (str): The user ID to filter conversations.
        sender (str): The sender type to filter conversations, default is "assistant".
    Returns:
        dict: A dictionary containing the search results.
    """
    search_responses = await search_client.search(
    {
        "requests": [
            {
                "indexName": INDEX_NAME,
                "query": query,
                "facetFilters": [
                    [f'user_id:{user_id}']
                ],
                "facetingAfterDistinct": True,
            }
        ]
    })

    hits = search_responses.results[0].actual_instance.hits

    conversations = []
    for hit in hits:
        title_highlight_obj = hit.highlight_result.get("title")
        content_highlight_obj = hit.highlight_result.get("content")

        highlight_title = hit.title

        if title_highlight_obj and title_highlight_obj.actual_instance.match_level != "none":
            highlight_title = title_highlight_obj.actual_instance.value
            snippet_result = getattr(hit, "snippet_result", None)
            if snippet_result and snippet_result.get("content"):
                snippet = snippet_result["content"].actual_instance.value
        else:
            if content_highlight_obj:
                snippet_result = getattr(hit, "snippet_result", None)
                if snippet_result and snippet_result.get("content"):
                    snippet = snippet_result["content"].actual_instance.value

        conversations.append({
            "conversation_id": hit.conversation_id,
            "title": highlight_title,
            "snippet": snippet,
            "last_message_timestamp": hit.timestamp
        })

    return {
        "query": query,
        "user_id": user_id,
        "conversations": conversations
    }