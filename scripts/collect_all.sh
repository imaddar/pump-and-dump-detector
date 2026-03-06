#!/bin/bash

echo "Starting data collection pipeline..."

python3 ingestion/binance_fetch.py
echo "Binance collection complete"

python3 ingestion/etherscan_fetch.py
echo "Etherscan collection complete"

echo "All collection scripts complete"