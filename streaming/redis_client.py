import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def check_redis_token(symbol: str, key_type: str):
    return bool(r.exists(f"{key_type}:{symbol}"))

def get_redis_symbol(symbol: str, key_type: str):
    
    pass
    
def set_redis_token(symbol: str, features: dict, key_type: str):
    ttl = 7200 if key_type == "pump" else 86400
    pass
