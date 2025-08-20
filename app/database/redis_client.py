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
    key_type = redis_client.type(name) 

    if key_type == "string":
        raw = redis_client.get(name)
        if raw is None:
            raise KeyError(f"Config '{name}' not found in Redis.")
        return json.loads(raw)

    elif key_type == "hash":
        data = redis_client.hgetall(name)
        if not data:
            raise KeyError(f"Config '{name}' not found in Redis.")
        return data

    else:
        raise TypeError(f"Unsupported Redis type for key '{name}': {key_type}")