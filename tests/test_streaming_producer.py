from unittest.mock import Mock, patch

from streaming.producer import run_once


@patch("streaming.producer.publish_baseline_snapshots")
@patch("streaming.producer.publish_pump_snapshots")
def test_run_once_flushes_after_publishing(mock_publish_pump, mock_publish_baseline):
    producer = Mock()

    run_once(producer, ["BTCUSDT"])

    mock_publish_baseline.assert_called_once_with(producer, ["BTCUSDT"])
    mock_publish_pump.assert_called_once_with(producer, ["BTCUSDT"])
    producer.flush.assert_called_once()
