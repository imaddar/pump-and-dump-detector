# Components of a Kafka stream

# Producers: these are applications that handle the data collection and push the information to the specific topic
# Topics: these are the data blocks that recieve the information from the producers and store them
# - Patitions: each topic can be partitiioned for more concurrency/parallelism
# Brokers: these handle the managing of the data within the topics; store and manage partitions, and handle read/writes from producers/consumers
# Consumers (Not relevant for this file): they are what reads from the Kafka topics, sending read requests

from kafka import KafkaProducer
import json
import schedule
from service.binance import get_pump_data, get_baseline_data
from datetime import datetime, timezone

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# list of symbols from watchlist.txt
symbols = []
with open('watchlist.txt', 'r') as file:
    for line in file:
        symbols.append(line.strip())


# function that calls fetch_pump and fetch_baseline over the entire watchlist
def fetch_pump():
    for symbol in symbols:
        pump_data, _, _ = get_pump_data(symbol, datetime.now())
        producer.send('pump_data', {
            'symbol': symbol,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'data': pump_data
        })
        

def fetch_baseline():
    for symbol in symbols:
        baseline_data = get_baseline_data(symbol, datetime.now())    
        producer.send('baseline_data', {
            'symbol': symbol,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'data': baseline_data
        })
    
# the specific fetching functions are done, now we need the scheduling
schedule.every(1).hours.do(fetch_pump)
schedule.every(1).days.do(fetch_baseline)

while True:
    schedule.run_pending()
    