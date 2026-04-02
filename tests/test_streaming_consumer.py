import json
from unittest.mock import Mock, patch

from streaming.consumer import handle_message


def build_message(topic: str, payload: dict, error=None):
    message = Mock()
    message.topic.return_value = topic
    message.error.return_value = error
    message.value.return_value = json.dumps(payload).encode("utf-8")
    return message


def test_handle_message_returns_false_for_kafka_error():
    message = build_message("pump_data", {"symbol": "BTCUSDT", "data": []}, error=Mock())

    assert handle_message(message) is False


@patch("streaming.consumer.set_redis_symbol")
@patch("streaming.consumer.get_redis_symbol", return_value=[[1]])
@patch("streaming.consumer.check_redis_symbol", return_value=True)
@patch("streaming.consumer.compute_features", return_value={"price_change_max": 1.0})
def test_handle_message_computes_and_caches_pump_features(
    mock_compute_features,
    mock_check_redis_symbol,
    mock_get_redis_symbol,
    mock_set_redis_symbol,
):
    payload = {"symbol": "BTCUSDT", "data": [[1, 2, 3]]}
    message = build_message("pump_data", payload)

    assert handle_message(message) is True
    mock_check_redis_symbol.assert_called_once_with("BTCUSDT", "baseline")
    mock_get_redis_symbol.assert_called_once_with("BTCUSDT", "baseline")
    mock_compute_features.assert_called_once()
    mock_set_redis_symbol.assert_called_once()


@patch("streaming.consumer.check_redis_symbol", return_value=False)
def test_handle_message_skips_pump_without_baseline(mock_check_redis_symbol):
    payload = {"symbol": "BTCUSDT", "data": [[1, 2, 3]]}
    message = build_message("pump_data", payload)

    assert handle_message(message) is False
    mock_check_redis_symbol.assert_called_once_with("BTCUSDT", "baseline")
