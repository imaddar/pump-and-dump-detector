from confluent_kafka import Consumer, KafkaError
import json
from features.feature_engineering import compute_features
from .redis_client import check_redis_symbol, get_redis_symbol, set_redis_symbol
import logging

conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-consumer-group',
    'auto.offset.reset': 'earliest'   
}

logger = logging.getLogger(__name__)

consumer = Consumer(conf)
consumer.subscribe(['pump_data', 'baseline_data'])

def handle_pump(msg):
    data = json.loads(msg.value().decode('utf-8'))
    symbol = data['symbol']
    if not check_redis_symbol(symbol, "baseline"):
        logger.warning(f"Baseline data for {symbol} not found in Redis. Skipping feature computation.")
        return
    features = compute_features(data['data'], get_redis_symbol(symbol, "baseline")) # compute features also needs baseline to compare against
    set_redis_symbol(symbol, features, "pump")
    
def handle_baseline(msg):
    data = json.loads(msg.value().decode('utf-8'))
    symbol = data['symbol']
    set_redis_symbol(symbol, data['data'], "baseline")


while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.topic() == 'pump_data':
        handle_pump(msg)
    elif msg.topic() == 'baseline_data':
        handle_baseline(msg)