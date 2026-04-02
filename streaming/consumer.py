from confluent_kafka import Consumer, KafkaError
import json
from features.feature_engineering import compute_features
from .redis_client import check_redis_symbol, get_redis_symbol, set_redis_symbol
import logging
from datetime import datetime, timezone

conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-consumer-group',
    'auto.offset.reset': 'earliest'   
}

logger = logging.getLogger(__name__)

def handle_pump(msg):
    data = json.loads(msg.value().decode('utf-8'))
    symbol = data['symbol']
    if not check_redis_symbol(symbol, "baseline"):
        logger.warning(f"Baseline data for {symbol} not found in Redis. Skipping feature computation.")
        return False
    baseline_payload = get_redis_symbol(symbol, "baseline")
    baseline_data = baseline_payload["data"] if isinstance(baseline_payload, dict) and "data" in baseline_payload else baseline_payload
    features = compute_features(data['data'], baseline_data) # compute features also needs baseline to compare against
    captured_at = data.get("fetched_at", datetime.now(timezone.utc).isoformat())
    set_redis_symbol(symbol, features, "pump", captured_at=captured_at)
    return True
    
def handle_baseline(msg):
    data = json.loads(msg.value().decode('utf-8'))
    symbol = data['symbol']
    captured_at = data.get("fetched_at", datetime.now(timezone.utc).isoformat())
    set_redis_symbol(symbol, data['data'], "baseline", captured_at=captured_at)
    return True


def handle_message(msg):
    if msg is None:
        return False
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            logger.info("Reached end of partition for topic %s", msg.topic())
            return False
        logger.error("Kafka consumer error on topic %s: %s", msg.topic(), msg.error())
        return False
    if msg.topic() == 'pump_data':
        return handle_pump(msg)
    if msg.topic() == 'baseline_data':
        return handle_baseline(msg)
    logger.warning("Received message on unexpected topic %s", msg.topic())
    return False


def create_consumer():
    consumer = Consumer(conf)
    consumer.subscribe(['pump_data', 'baseline_data'])
    return consumer


def run_forever(consumer):
    try:
        while True:
            msg = consumer.poll(1.0)
            handle_message(msg)
    except KeyboardInterrupt:
        logger.info("Stopping Kafka consumer")
    finally:
        consumer.close()


def main():
    run_forever(create_consumer())


if __name__ == "__main__":
    main()
