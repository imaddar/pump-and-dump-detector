import pytest
import json
from pathlib import Path
import lightgbm as lgb
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split

metadata = json.load(Path("modeling/models/lgbm_tuned.json").open("r"))

def load_data():
    df = pd.read_parquet("data/processed/features/features.parquet")
    df = df.select_dtypes(include=np.number)
    X = df.drop(columns=["success"])
    y = df["success"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    

def test_model_quality():
    model = lgb.Booster(model_file="modeling/models/lgbm_tuned.txt")
    _, X_val, _, y_val = load_data()
    
    #predict
    y_prob = model.predict(X_val)
    
    precision, recall, thresholds = precision_recall_curve(y_val, y_prob)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
    
    new_pr_auc = average_precision_score(y_val, y_prob)
    new_f1 = f1_scores.max()
    
    curr_pr_auc = metadata["pr_auc"]
    curr_f1 = metadata["f1"]
    
    assert new_pr_auc >= curr_pr_auc - 0.001
    assert new_f1 >= curr_f1 - 0.001