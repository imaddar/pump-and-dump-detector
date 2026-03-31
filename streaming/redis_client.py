import redis
import json
import os

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True)

def check_redis_symbol(symbol: str, key_type: str):
    return bool(r.exists(f"{key_type}:{symbol}"))

def get_redis_symbol(symbol: str, key_type: str):
    data = r.get(f"{key_type}:{symbol}")
    return json.loads(data) if data else None
    
def set_redis_symbol(symbol: str, features: dict, key_type: str):
    ttl = 7200 if key_type == "pump" else 86400
    r.setex(f"{key_type}:{symbol}", ttl, json.dumps(features))
