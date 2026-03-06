
import logging
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split

# ── paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHAP_DIR = PROJECT_ROOT / "modeling" / "models" / "shap"
SHAP_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)

# ── logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "logs" / "shap_analysis.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── load model ────────────────────────────────────────────────────────────────
model_path = PROJECT_ROOT / "modeling" / "models" / "lgbm_tuned.txt"
model = lgb.Booster(model_file=str(model_path))
logger.info(f"Model loaded from {model_path}")

# ── load data and reproduce val split ─────────────────────────────────────────
df = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "features" / "features.parquet")
df = df.select_dtypes(include=np.number)
X = df.drop(columns=["success"])
y = df["success"]

# must use same random_state as training to get identical val split
_, X_val, _, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
logger.info(f"Val size: {len(X_val)}  |  Positive rate: {y_val.mean():.3f}")

# ── compute SHAP values ───────────────────────────────────────────────────────
logger.info("Computing SHAP values...")
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_val)

# newer SHAP versions return a list [class_0_values, class_1_values]
# we want class 1 (pump)
if isinstance(shap_values, list):
    shap_vals = shap_values[1]
    expected_value = explainer.expected_value[1]
else:
    shap_vals = shap_values
    expected_value = explainer.expected_value

logger.info("SHAP values computed")

# ── summary plot ──────────────────────────────────────────────────────────────
# every prediction as a dot — shows direction and magnitude of each feature
shap.summary_plot(shap_vals, X_val, show=False)
plt.tight_layout()
plt.savefig(SHAP_DIR / "summary_plot.png", dpi=150, bbox_inches="tight")
plt.close()
logger.info(f"Saved {SHAP_DIR / 'summary_plot.png'}")

# ── feature importance bar plot ───────────────────────────────────────────────
# mean absolute SHAP value per feature — clean bar chart
shap.summary_plot(shap_vals, X_val, plot_type="bar", show=False)
plt.tight_layout()
plt.savefig(SHAP_DIR / "feature_importance.png", dpi=150, bbox_inches="tight")
plt.close()
logger.info(f"Saved {SHAP_DIR / 'feature_importance.png'}")

# ── waterfall plot — highest confidence pump prediction ───────────────────────
y_prob = model.predict(X_val)
highest_pump_idx = y_prob.argmax()

shap_explanation = shap.Explanation(
    values=shap_vals[highest_pump_idx],
    base_values=expected_value,
    data=X_val.iloc[highest_pump_idx],
    feature_names=X_val.columns.tolist()
)
shap.plots.waterfall(shap_explanation, show=False)
plt.tight_layout()
plt.savefig(SHAP_DIR / "waterfall_top_prediction.png", dpi=150, bbox_inches="tight")
plt.close()
logger.info(f"Saved {SHAP_DIR / 'waterfall_top_prediction.png'}")

logger.info(f"SHAP analysis complete — plots saved to {SHAP_DIR}")