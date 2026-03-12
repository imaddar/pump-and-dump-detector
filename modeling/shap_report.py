import logging
from pathlib import Path

from modeling.shap_analysis import (
    DEFAULT_MODEL_PATH,
    DEFAULT_SHAP_DIR,
    build_tree_explainer,
    build_waterfall_explanation,
    compute_shap_values,
    load_model,
    load_validation_data,
    save_feature_importance_plot,
    save_summary_plot,
    save_waterfall_plot,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "shap_analysis.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    DEFAULT_SHAP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    logger.info("Loading model from %s", DEFAULT_MODEL_PATH)
    model = load_model()

    logger.info("Loading validation data")
    X_val, y_val = load_validation_data()
    logger.info("Val size: %s  |  Positive rate: %.3f", len(X_val), y_val.mean())

    logger.info("Computing SHAP values")
    explainer = build_tree_explainer(model)
    shap_values, expected_value = compute_shap_values(explainer, X_val)
    logger.info("SHAP values computed")

    summary_path = save_summary_plot(shap_values, X_val, DEFAULT_SHAP_DIR / "summary_plot.png")
    logger.info("Saved %s", summary_path)

    importance_path = save_feature_importance_plot(
        shap_values,
        X_val,
        DEFAULT_SHAP_DIR / "feature_importance.png",
    )
    logger.info("Saved %s", importance_path)

    y_prob = model.predict(X_val)
    highest_pump_idx = y_prob.argmax()
    explanation = build_waterfall_explanation(
        shap_values_row=shap_values[highest_pump_idx],
        expected_value=expected_value,
        feature_row=X_val.iloc[highest_pump_idx],
    )
    waterfall_path = save_waterfall_plot(
        explanation,
        DEFAULT_SHAP_DIR / "waterfall_top_prediction.png",
    )
    logger.info("Saved %s", waterfall_path)

    logger.info("SHAP analysis complete")


if __name__ == "__main__":
    main()
