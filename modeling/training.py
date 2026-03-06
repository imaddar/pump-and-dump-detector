import pandas as pd
import lightgbm as lgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from pathlib import Path
import optuna
# import optuna.integration.lightgbm as lgb_optuna

df = pd.read_parquet("data/processed/features/features.parquet")

df = df.select_dtypes(include=np.number)
X, y = df.drop(columns=["success"]), df["success"]
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)


X_train = lgb.Dataset(X_train, label=y_train)
X_val_lgb = lgb.Dataset(X_val, label=y_val)

X_train.save_binary(Path("./data/processed/features/X_train.bin"))

param = {"objective": "binary"}
param["metric"] = "auc"

bst = lgb.train(param, X_train, valid_sets=[X_val_lgb])

bst.save_model(Path("./modeling/models/lgbm_model.txt"))

y_prob = bst.predict(X_val)
y_pred = (y_prob >= 0.5).astype(int)
print("AUC:", roc_auc_score(y_val, y_prob))
print(classification_report(y_val, y_pred))
print("Confusion Matrix:", confusion_matrix(y_val, y_pred))