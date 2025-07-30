from app.database.redis_client import get_redis_config
from app.schemas.conversations import ProcessedMessage
from tavily import AsyncTavilyClient

# -------------------- Web Search Service Functions --------------------
api_keys = get_redis_config("api_keys")
tavily_client = AsyncTavilyClient(api_key=api_keys["TAVILY_API_KEY"])

async def search(query: str):
    """    
    This function sanitizes the query, performs the search, and formats the results.
    Args:
        query (str): The search query.
    Returns:
        list: A list of formatted search results.
    Raises:
        ValueError: If the query is empty or exceeds length constraints.
    """
    sanitized_query = sanitize_query(query)
    search_results = await tavily_client.search(
        query=sanitized_query,
        search_depth="advanced",
        max_results=5
    )

    return ProcessedMessage(
        content=query,
        context=[f"{result['title']}: {result['content']} ({result['url']})" for result in search_results["results"]],
        images=None,
        recent_conversations=None
    )


def sanitize_query(query: str) -> str:
    """
    Sanitize the search query to ensure it meets length and format requirements.
    Args:
        query (str): The raw search query.
    Returns:
        str: A sanitized version of the query.
    Raises:
        ValueError: If the query is empty or exceeds length constraints.
    """
    # Strip leading/trailing whitespace and remove control chars
    query = query.strip().replace("\n", " ").replace("\r", " ")

    # Enforce length constraints
    if len(query) < 1:
        raise ValueError("Query must be at least 1 character long")
    if len(query) > 400:
        query = query[:400]

    return query





