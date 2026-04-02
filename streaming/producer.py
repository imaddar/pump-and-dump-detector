from kafka import KafkaProducer
import json
import schedule
from service.binance import get_pump_data, get_baseline_data
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
WATCHLIST_PATH = Path(__file__).resolve().parent / "watchlist.txt"


def create_producer():
    return KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[str]:
    with path.open("r") as file:
        return [line.strip() for line in file if line.strip()]


# function that calls fetch_pump and fetch_baseline over the entire watchlist
def publish_pump_snapshots(producer, symbols: list[str]):
    for symbol in symbols:
        pump_data, _, _ = get_pump_data(symbol, datetime.now())
        producer.send('pump_data', {
            'symbol': symbol,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'data': pump_data
        })
        

def publish_baseline_snapshots(producer, symbols: list[str]):
    for symbol in symbols:
        baseline_data = get_baseline_data(symbol, datetime.now())    
        producer.send('baseline_data', {
            'symbol': symbol,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'data': baseline_data
        })


def run_once(producer, symbols: list[str]):
    publish_baseline_snapshots(producer, symbols)
    publish_pump_snapshots(producer, symbols)
    producer.flush()


def run_forever(producer, symbols: list[str]):
    schedule.every(1).hours.do(lambda: publish_pump_snapshots(producer, symbols))
    schedule.every(1).days.do(lambda: publish_baseline_snapshots(producer, symbols))
    try:
        run_once(producer, symbols)
        while True:
            schedule.run_pending()
    except KeyboardInterrupt:
        logger.info("Stopping Kafka producer")
    finally:
        producer.flush()
        producer.close()


def main():
    run_forever(create_producer(), load_watchlist())


if __name__ == "__main__":
    main()
    
