import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

# ── logging setup ─────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("data/processed/features", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler("logs/build_features.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── can