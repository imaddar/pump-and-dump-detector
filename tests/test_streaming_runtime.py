from unittest.mock import Mock

from streaming.consumer import run_until


def test_run_until_stops_after_target_processed_messages():
    consumer = Mock()
    consumer.poll.side_effect = ["msg1", "msg2"]

    handled = []

    def handle_message(message):
        handled.append(message)
        return True

    processed = run_until(
        consumer,
        target_processed=2,
        idle_limit=5,
        handle_message_fn=handle_message,
    )

    assert processed == 2
    assert handled == ["msg1", "msg2"]
    consumer.close.assert_called_once()


def test_run_until_stops_after_idle_limit():
    consumer = Mock()
    consumer.poll.side_effect = [None, None, None]

    processed = run_until(
        consumer,
        target_processed=5,
        idle_limit=3,
        handle_message_fn=lambda message: False,
    )

    assert processed == 0
    consumer.close.assert_called_once()
