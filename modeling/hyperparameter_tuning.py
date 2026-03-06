import logging
import os
from pathlib import Path

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split

optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── logging setup ─────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("models", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler("logs/train.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ── load data once ────────────────────────────────────────────────────────────
def load_data():
    df = pd.read_parquet("data/processed/features/features.parquet")
    df = df.select_dtypes(include=np.number)
    X = df.drop(columns=["success"])
    y = df["success"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)


X_train, X_val, y_train, y_val = load_data()
logger.info(f"Train size: {len(X_train)}  |  Val size: {len(X_val)}")
logger.info(f"Positive rate — train: {y_train.mean():.3f}  val: {y_val.mean():.3f}")

lgb_train = lgb.Dataset(X_train, label=y_train)
lgb_val   = lgb.Dataset(X_val,   label=y_val, reference=lgb_train)


# ── optuna objective ──────────────────────────────────────────────────────────
def objective(trial: optuna.Trial) -> float:
    params = {
        "objective":        "binary",
        "metric":           "average_precision",
        "boosting_type":    "gbdt",
        "verbosity":        -1,
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "num_leaves":       trial.suggest_int("num_leaves", 20, 150),
        "max_depth":        trial.suggest_int("max_depth", 3, 8),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 10.0),
        "min_child_samples":trial.suggest_int("min_child_samples", 10, 100),
        "reg_alpha":        trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda":       trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "subsample":        trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "feature_pre_filter": False,
    }

    n_estimators = trial.suggest_int("n_estimators", 100, 1000)

    bst = lgb.train(
        params,
        lgb_train,
        num_boost_round=n_estimators,
        valid_sets=[lgb_val],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50, verbose=False),
            lgb.log_evaluation(period=-1),
        ],
    )

    y_prob = bst.predict(X_val)
    return average_precision_score(y_val, y_prob)


# ── run tuning ────────────────────────────────────────────────────────────────
logger.info("Starting Optuna hyperparameter search (50 trials)...")

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=50, catch=(Exception,))

logger.info(f"Best PR-AUC:  {study.best_value:.4f}")
logger.info(f"Best params:  {study.best_params}")


# ── retrain final model with best params ──────────────────────────────────────
logger.info("Retraining final model with best params...")

best_params = {
    "objective":        "binary",
    "metric":           "average_precision",
    "boosting_type":    "gbdt",
    "verbosity":        -1,
    **{k: v for k, v in study.best_params.items() if k != "n_estimators"},
}

final_model = lgb.train(
    best_params,
    lgb_train,
    num_boost_round=study.best_params["n_estimators"],
    valid_sets=[lgb_val],
    callbacks=[
        lgb.early_stopping(stopping_rounds=50, verbose=False),
        lgb.log_evaluation(period=10),
    ],
)


# ── evaluate ──────────────────────────────────────────────────────────────────
y_prob = final_model.predict(X_val)

precision, recall, thresholds = precision_recall_curve(y_val, y_prob)
f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
best_threshold = thresholds[f1_scores.argmax()]
logger.info(f"Best threshold: {best_threshold:.3f}  |  Best F1: {f1_scores.max():.3f}")

# use best threshold instead of 0.5
y_pred = (y_prob >= best_threshold).astype(int)

pr_auc = average_precision_score(y_val, y_prob)

logger.info(f"\nPR-AUC: {pr_auc:.4f}")
logger.info(f"\n{classification_report(y_val, y_pred)}")
logger.info(f"\nConfusion Matrix:\n{confusion_matrix(y_val, y_pred)}")


# ── save model ────────────────────────────────────────────────────────────────
model_path = Path("modeling/models/lgbm_tuned.txt")
final_model.save_model(str(model_path))
logger.info(f"Model saved to {model_path}")