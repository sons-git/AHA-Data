from typing import List
from app.database.redis_client import get_redis_config
from tavily import AsyncTavilyClient

# -------------------- Web Search Service Functions --------------------
api_keys = get_redis_config("api_keys")
tavily_client = AsyncTavilyClient(api_key=api_keys["TAVILY_API_KEY"])

async def search(query: str, conversation_history: str):
    """    
    This function sanitizes the query, performs the search, and formats the results.
    Args:
        query (str): The search query.
    Returns:
        tuple: (structured_results, formatted_results)
    Raises:
        ValueError: If the query is empty or exceeds length constraints.
    """
    sanitized_query = sanitize_query(query)
    search_results = await tavily_client.search(
        query=sanitized_query,
        max_results=7,
        country="vietnam",
        start_date="2025-01-01",
        context=conversation_history
    )

    items = search_results.get("results", [])

    structured_results = [
        {
            "title": item.get("title", ""),
            "snippet": item.get("content", ""), 
            "url": item.get("url", "")
        }
        for item in items
    ]

    formatted_results = [
        (
            f"Web Search Result {i+1}:\n"
            f"  Title: {r['title']}\n"
            f"  Snippet: {r['snippet']}\n"
            f"  URL: {r['url']}"
        )
        for i, r in enumerate(structured_results)
    ]

    return structured_results, formatted_results


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
    if not query:
        raise ValueError("Query cannot be empty")
    # Strip leading/trailing whitespace and remove control chars
    query = query.strip().replace("\n", " ").replace("\r", " ")

    # Enforce length constraints
    if len(query) > 400:
        query = query[:400]

    return query





