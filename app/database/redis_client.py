import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    username="default",
    decode_responses=True
)

def get_redis_config(name: str) -> dict:
    """
    Retrieve and parse a JSON configuration stored in Redis.

    Args:
        name (str): Redis key name.

    Returns:
        dict: Parsed configuration dictionary.

    Raises:
        KeyError: If the key does not exist in Redis.
        json.JSONDecodeError: If the stored value is not valid JSON.
    """
    raw = redis_client.get(name=name)
    if raw is None:
        raise KeyError(f"Config '{name}' not found in Redis.")
    return json.loads(raw)