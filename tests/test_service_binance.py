from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests

from service.binance import BinanceConnectionError, get_pump_data


def build_response(status_code: int = 200, payload: list | dict | None = None) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else []
    return response


@patch("service.binance.requests.get")
@patch("service.binance.time.sleep")
def test_get_pump_data_retries_after_connection_error(mock_sleep, mock_get):
    pump_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_get.side_effect = [
        requests.exceptions.ConnectionError(),
        build_response(payload=[[1, "1", "1", "1", "1", "1", 2, "1", 1, "1", "1", "0"]]),
    ]

    data, _, _ = get_pump_data("BTCUSDT", pump_time)

    assert len(data) == 1
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("service.binance.requests.get")
@patch("service.binance.time.sleep")
def test_get_pump_data_raises_after_retry_exhaustion(mock_sleep, mock_get):
    pump_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_get.side_effect = requests.exceptions.ConnectionError()

    try:
        get_pump_data("BTCUSDT", pump_time)
    except BinanceConnectionError as exc:
        assert "BTCUSDT" in str(exc)
    else:
        raise AssertionError("Expected BinanceConnectionError")

    assert mock_get.call_count > 1
    assert mock_sleep.call_count == mock_get.call_count - 1
