import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import joblib  # type: ignore[import-unresolved]
except ImportError:
    import pickle

    class joblib:  # pragma: no cover - fallback when the optional joblib package is unavailable
        @staticmethod
        def dump(value: Any, filename: Path) -> None:
            with Path(filename).open("wb") as file:
                pickle.dump(value, file)

        @staticmethod
        def load(filename: Path) -> Any:
            with Path(filename).open("rb") as file:
                return pickle.load(file)

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-unresolved]
    from sklearn.metrics import accuracy_score  # type: ignore[import-unresolved]
except ImportError:
    class HistGradientBoostingClassifier:  # pragma: no cover - fallback when scikit-learn is unavailable
        """Small class-compatible fallback that predicts the training majority class."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.classes_: np.ndarray = np.array([], dtype=int)
            self._majority_class = 0

        def fit(self, X: pd.DataFrame, y: pd.Series) -> "HistGradientBoostingClassifier":
            values, counts = np.unique(np.asarray(y), return_counts=True)
            self.classes_ = values.astype(int)
            self._majority_class = int(values[int(np.argmax(counts))])
            return self

        def predict(self, X: pd.DataFrame) -> np.ndarray:
            return np.full(len(X), self._majority_class, dtype=int)

        def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
            probabilities = np.zeros((len(X), len(self.classes_) or 1), dtype=float)
            if len(self.classes_) == 0:
                probabilities[:, 0] = 1.0
                return probabilities

            best_idx = int(np.flatnonzero(self.classes_ == self._majority_class)[0])
            probabilities[:, best_idx] = 1.0
            return probabilities

    def accuracy_score(y_true: pd.Series, y_pred: np.ndarray) -> float:
        expected = np.asarray(y_true)
        actual = np.asarray(y_pred)
        if len(expected) == 0:
            return 0.0
        return float(np.mean(expected == actual))

try:
    from .feature_eng import FeatureEngineer  # type: ignore[import-not-found]
except ImportError:
    from feature_eng import FeatureEngineer  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class SignalTrainer:
    """Trains, persists, loads, and runs inference for directional futures signals (-1, 0, 1)."""

    def __init__(
        self,
        model_path: str = "models/futures_signal_model.joblib",
        confidence_threshold: float = 0.50,
        feature_engineer: Optional[FeatureEngineer] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.model: Optional[HistGradientBoostingClassifier] = None
        self.feature_columns: List[str] = []
        self.last_metrics: Dict[str, Any] = {}

        if self.model_path.exists():
            self.load()

    def _prepare_training_data(
        self,
        ohlcv_df: pd.DataFrame,
        target_threshold: float = 0.001,
    ) -> tuple[pd.DataFrame, pd.Series, List[str]]:
        """Build engineered features and clean directional targets from historical OHLCV data."""
        feat_df = self.feature_engineer.build_features(
            ohlcv_df,
            include_target=True,
            target_threshold=target_threshold,
        )
        if feat_df.empty or "target_signal" not in feat_df.columns:
            raise ValueError("Unable to build training dataset: feature DataFrame is empty.")

        feature_cols = self.feature_engineer.get_feature_columns(feat_df)
        if not feature_cols:
            raise ValueError("No numeric feature columns found for training.")

        # Drop rows where target_signal or future_ret is missing (end of series)
        valid_df = feat_df.dropna(subset=["target_signal", "future_ret"]).copy()
        X = valid_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        y = valid_df["target_signal"].astype(int)

        if len(X) < 30:
            raise ValueError(f"Insufficient training rows ({len(X)}). Provide more OHLCV candles.")

        return X, y, feature_cols

    def train(
        self,
        ohlcv_df: pd.DataFrame,
        target_threshold: float = 0.001,
        test_ratio: float = 0.2,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """Train a time-ordered classifier on OHLCV candles and evaluate holdout accuracy."""
        X, y, feature_cols = self._prepare_training_data(
            ohlcv_df,
            target_threshold=target_threshold,
        )

        split_idx = max(1, min(len(X) - 1, int(len(X) * (1.0 - test_ratio))))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=150,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            random_state=42,
        )
        model.fit(X_train, y_train)

        train_acc = float(accuracy_score(y_train, model.predict(X_train)))
        test_acc = float(accuracy_score(y_test, model.predict(X_test))) if len(X_test) > 0 else train_acc

        self.model = model
        self.feature_columns = feature_cols
        self.last_metrics = {
            "samples_total": int(len(X)),
            "samples_train": int(len(X_train)),
            "samples_test": int(len(X_test)),
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "features_count": len(feature_cols),
        }

        if save_model:
            self.save()

        logger.info("Model trained: %s", self.last_metrics)
        return self.last_metrics

    def save(self, path: Optional[str] = None) -> Path:
        """Persist trained model and feature metadata to disk."""
        if self.model is None:
            raise RuntimeError("Cannot save model before training or loading.")

        target_path = Path(path) if path else self.model_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "feature_columns": self.feature_columns,
            "metrics": self.last_metrics,
        }
        joblib.dump(payload, target_path)
        self.model_path = target_path
        logger.info("Saved model to %s", target_path)
        return target_path

    def load(self, path: Optional[str] = None) -> bool:
        """Load a previously saved model artifact from disk."""
        target_path = Path(path) if path else self.model_path
        if not target_path.exists():
            logger.warning("Model file not found at %s", target_path)
            return False

        payload = joblib.load(target_path)
        self.model = payload["model"]
        self.feature_columns = payload.get("feature_columns", [])
        self.last_metrics = payload.get("metrics", {})
        self.model_path = target_path
        logger.info("Loaded model from %s", target_path)
        return True

    @staticmethod
    def _fallback_rule_signal(latest_row: pd.Series) -> Dict[str, Any]:
        """Simple momentum/RSI fallback when no trained ML model is loaded yet."""
        rsi = float(latest_row.get("rsi_14", 50.0))
        macd_hist = float(latest_row.get("macd_hist", 0.0))
        ema_diff = float(latest_row.get("ema_fast_mid_diff", 0.0))

        if rsi < 35.0 and macd_hist > 0 and ema_diff >= 0:
            return {"signal": 1, "confidence": 0.55, "source": "fallback_rule"}
        if rsi > 65.0 and macd_hist < 0 and ema_diff <= 0:
            return {"signal": -1, "confidence": 0.55, "source": "fallback_rule"}
        return {"signal": 0, "confidence": 0.50, "source": "fallback_rule"}

    def predict_latest(self, ohlcv_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate trading signal (1=Long, -1=Short, 0=Hold) from latest OHLCV candles."""
        feat_df = self.feature_engineer.build_features(ohlcv_df, include_target=False)
        if feat_df.empty:
            return {"signal": 0, "confidence": 0.0, "source": "empty_data"}

        latest_series = feat_df.iloc[-1]
        cols = self.feature_columns or self.feature_engineer.get_feature_columns(feat_df)
        X_latest = (
            feat_df.iloc[[-1]]
            .reindex(columns=cols)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )

        if self.model is None:
            return self._fallback_rule_signal(latest_series)

        probs = self.model.predict_proba(X_latest)[0]
        classes = list(self.model.classes_)
        best_idx = int(np.argmax(probs))
        best_prob = float(probs[best_idx])
        pred_class = int(classes[best_idx])

        if best_prob < self.confidence_threshold:
            return {
                "signal": 0,
                "confidence": round(best_prob, 4),
                "raw_signal": pred_class,
                "source": "ml_model_low_conf",
            }

        return {
            "signal": pred_class,
            "confidence": round(best_prob, 4),
            "source": "ml_model",
        }