import logging
from pathlib import Path
from typing import Any

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "modeling" / "models" / "lgbm_tuned.txt"
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "features" / "features.parquet"
DEFAULT_SHAP_DIR = PROJECT_ROOT / "modeling" / "models" / "shap"

logger = logging.getLogger(__name__)


def load_model(model_path: Path | str = DEFAULT_MODEL_PATH) -> lgb.Booster:
    return lgb.Booster(model_file=str(model_path))


def load_validation_data(
    data_path: Path | str = DEFAULT_DATA_PATH,
    target_column: str = "success",
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_parquet(data_path)
    df = df.select_dtypes(include=np.number)
    X = df.drop(columns=[target_column])
    y = df[target_column]
    _, X_val, _, y_val = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )
    return X_val, y_val


def build_tree_explainer(model: lgb.Booster) -> shap.TreeExplainer:
    return shap.TreeExplainer(model)


def normalize_binary_shap_output(
    shap_values: Any,
    expected_value: Any,
) -> tuple[np.ndarray, Any]:
    if isinstance(shap_values, list):
        normalized_values = np.asarray(shap_values[1])
        normalized_expected_value = expected_value[1]
    else:
        normalized_values = np.asarray(shap_values)
        normalized_expected_value = expected_value
    return normalized_values, normalized_expected_value


def compute_shap_values(
    explainer: shap.TreeExplainer,
    features: pd.DataFrame,
) -> tuple[np.ndarray, Any]:
    shap_values = explainer.shap_values(features)
    return normalize_binary_shap_output(shap_values, explainer.expected_value)


def get_top_feature_impacts(
    shap_values_row: np.ndarray,
    feature_names: list[str],
    feature_values: pd.Series | None = None,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    if top_n <= 0:
        return []

    ranked_indices = np.argsort(np.abs(shap_values_row))[::-1][:top_n]
    impacts: list[dict[str, Any]] = []
    for index in ranked_indices:
        impact = {
            "feature": feature_names[index],
            "shap_value": float(shap_values_row[index]),
        }
        if feature_values is not None:
            impact["feature_value"] = float(feature_values.iloc[index])
        impacts.append(impact)
    return impacts


def get_top_feature_names(
    shap_values_row: np.ndarray,
    feature_names: list[str],
    top_n: int = 3,
) -> list[str]:
    return [
        impact["feature"]
        for impact in get_top_feature_impacts(
            shap_values_row=shap_values_row,
            feature_names=feature_names,
            top_n=top_n,
        )
    ]


def build_waterfall_explanation(
    shap_values_row: np.ndarray,
    expected_value: Any,
    feature_row: pd.Series,
) -> shap.Explanation:
    return shap.Explanation(
        values=shap_values_row,
        base_values=expected_value,
        data=feature_row,
        feature_names=feature_row.index.tolist(),
    )


def save_summary_plot(
    shap_values: np.ndarray,
    features: pd.DataFrame,
    output_path: Path | str,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shap.summary_plot(shap_values, features, show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def save_feature_importance_plot(
    shap_values: np.ndarray,
    features: pd.DataFrame,
    output_path: Path | str,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shap.summary_plot(shap_values, features, plot_type="bar", show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def save_waterfall_plot(
    explanation: shap.Explanation,
    output_path: Path | str,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shap.plots.waterfall(explanation, show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path
