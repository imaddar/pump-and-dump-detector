from datetime import datetime, timezone

import service.app as service_app
from service.app import app


def benchmark_resolve_symbol(symbol: str) -> str:
    return symbol


def benchmark_get_pump_data(symbol: str, pump_time: datetime):
    raise RuntimeError("Integration benchmark app should use warm Redis cache, not live pump fetches")


def benchmark_get_baseline_data(symbol: str, pump_time: datetime):
    raise RuntimeError("Integration benchmark app should use warm Redis cache, not live baseline fetches")


service_app.resolve_symbol = benchmark_resolve_symbol
service_app.get_pump_data = benchmark_get_pump_data
service_app.get_baseline_data = benchmark_get_baseline_data
