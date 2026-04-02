import redis
import json
import os
from datetime import datetime, timezone

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True)
PUMP_TTL_SECONDS = 7200
BASELINE_TTL_SECONDS = 86400

def check_redis_symbol(symbol: str, key_type: str):
    return bool(r.exists(f"{key_type}:{symbol}"))

def get_redis_symbol(symbol: str, key_type: str):
    data = r.get(f"{key_type}:{symbol}")
    return json.loads(data) if data else None


def build_cache_payload(data, key_type: str, captured_at: datetime | None = None):
    captured_at = captured_at or datetime.now(timezone.utc)
    if isinstance(captured_at, datetime):
        captured_at = captured_at.astimezone(timezone.utc).isoformat()

    payload_key = "features" if key_type == "pump" else "data"
    return {
        payload_key: data,
        "computed_at": captured_at,
        "cache_type": key_type,
    }


def set_redis_symbol(symbol: str, data, key_type: str, captured_at: datetime | None = None):
    ttl = PUMP_TTL_SECONDS if key_type == "pump" else BASELINE_TTL_SECONDS
    payload = build_cache_payload(data, key_type, captured_at=captured_at)
    r.setex(f"{key_type}:{symbol}", ttl, json.dumps(payload))
