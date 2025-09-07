import httpx
from typing import List
from app.database.redis_client import get_redis_config
from app.schemas.conversations import ProcessedMessage

api_keys = get_redis_config("api_keys")
API_KEY = api_keys["SEARCH_API_KEY"] 
CX = api_keys["SEARCH_CX"] 

async def search(query: str):
    """
    Perform a Google Custom Search and format the results.
    Args:
        query (str): The search query.
    Returns:
        ProcessedMessage: formatted search results
    Raises:
        ValueError: If the query is empty or exceeds length constraints.
    """
    sanitized_query = sanitize_query(query)

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": sanitized_query,
        "safe": "active",  # Ensure safe search
        "num": 5   # limit results
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    items = data.get("items", [])

    structured_results = [
        {
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "link": item.get("link", "")
        }
        for item in items
    ]

    formatted_results = [
        f"Web Search Result {i+1}: Title: {r['title']} | Snippet: {r['snippet']} | Link: {r['link']}"
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





