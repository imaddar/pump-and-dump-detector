from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from service.app import get_cached_feature_dict


@patch("service.app.get_redis_symbol")
@patch("service.app.check_redis_symbol", return_value=True)
def test_get_cached_feature_dict_returns_feature_payload_when_fresh(
    mock_check_redis_symbol,
    mock_get_redis_symbol,
):
    now = datetime.now(timezone.utc)
    mock_get_redis_symbol.return_value = {
        "computed_at": now.isoformat(),
        "features": {"price_change_max": 0.4},
    }

    feature_dict = get_cached_feature_dict("BTCUSDT", now)

    assert feature_dict == {"price_change_max": 0.4}


@patch("service.app.get_redis_symbol")
@patch("service.app.check_redis_symbol", return_value=True)
def test_get_cached_feature_dict_rejects_stale_cache(
    mock_check_redis_symbol,
    mock_get_redis_symbol,
):
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(hours=3)
    mock_get_redis_symbol.return_value = {
        "computed_at": stale_time.isoformat(),
        "features": {"price_change_max": 0.4},
    }

    try:
        get_cached_feature_dict("BTCUSDT", now)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("Expected HTTPException for stale cache")
