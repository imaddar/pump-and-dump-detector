from unittest.mock import Mock, patch

from streaming.producer import publish_pump_snapshots, run_once


@patch("streaming.producer.publish_baseline_snapshots")
@patch("streaming.producer.publish_pump_snapshots")
def test_run_once_flushes_after_publishing(mock_publish_pump, mock_publish_baseline):
    producer = Mock()

    run_once(producer, ["BTCUSDT"])

    mock_publish_baseline.assert_called_once_with(producer, ["BTCUSDT"])
    mock_publish_pump.assert_called_once_with(producer, ["BTCUSDT"])
    producer.flush.assert_called_once()


@patch("streaming.producer.fetch_pump_snapshot")
def test_publish_pump_snapshots_uses_symbol_as_message_key(mock_fetch_pump_snapshot):
    producer = Mock()
    mock_fetch_pump_snapshot.return_value = ("BTCUSDT", {"symbol": "BTCUSDT", "data": []})

    publish_pump_snapshots(producer, ["BTCUSDT"], max_workers=2)

    producer.send.assert_called_once()
    assert producer.send.call_args.kwargs["key"] == b"BTCUSDT"
