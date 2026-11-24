import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_OHLCV_COLS = ("timestamp", "open", "high", "low", "close", "volume")


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index (Wilder-style EMA smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD line, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": histogram,
        },
        index=series.index,
    )


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute Average True Range (ATR)."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


class FeatureEngineer:
    """Transforms raw OHLCV candle DataFrames into engineered features for trading & ML."""

    def __init__(
        self,
        rsi_period: int = 14,
        atr_period: int = 14,
        ema_fast: int = 9,
        ema_mid: int = 21,
        ema_slow: int = 50,
        vol_window: int = 20,
        horizon: int = 1,
        drop_na: bool = False,
    ) -> None:
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.ema_fast = ema_fast
        self.ema_mid = ema_mid
        self.ema_slow = ema_slow
        self.vol_window = vol_window
        self.horizon = horizon
        self.drop_na = drop_na

    @staticmethod
    def _validate_df(df: pd.DataFrame) -> pd.DataFrame:
        missing = [col for col in REQUIRED_OHLCV_COLS if col not in df.columns]
        if missing:
            raise ValueError(f"DataFrame missing required OHLCV columns: {missing}")

        out = df.copy()
        for col in ("open", "high", "low", "close", "volume"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out = out.sort_values("timestamp").reset_index(drop=True)
        return out

    def build_features(
        self,
        df: pd.DataFrame,
        include_target: bool = False,
        target_threshold: float = 0.001,
    ) -> pd.DataFrame:
        """Add technical indicators, price action ratios, and optional training targets."""
        if df is None or df.empty:
            logger.warning("Received empty OHLCV DataFrame in build_features.")
            return pd.DataFrame()

        data = self._validate_df(df)
        close = data["close"]
        high = data["high"]
        low = data["low"]
        open_p = data["open"]
        volume = data["volume"]

        # Returns & momentum
        data["ret_1"] = close.pct_change(1)
        data["ret_3"] = close.pct_change(3)
        data["ret_5"] = close.pct_change(5)
        data["log_ret_1"] = np.log(close / close.shift(1).replace(0.0, np.nan))

        # Moving averages & trend spreads
        data[f"ema_{self.ema_fast}"] = close.ewm(span=self.ema_fast, adjust=False).mean()
        data[f"ema_{self.ema_mid}"] = close.ewm(span=self.ema_mid, adjust=False).mean()
        data[f"ema_{self.ema_slow}"] = close.ewm(span=self.ema_slow, adjust=False).mean()

        data["ema_fast_mid_diff"] = (data[f"ema_{self.ema_fast}"] - data[f"ema_{self.ema_mid}"]) / close.replace(0.0, np.nan)
        data["ema_mid_slow_diff"] = (data[f"ema_{self.ema_mid}"] - data[f"ema_{self.ema_slow}"]) / close.replace(0.0, np.nan)
        data["price_vs_ema_mid"] = (close - data[f"ema_{self.ema_mid}"]) / data[f"ema_{self.ema_mid}"].replace(0.0, np.nan)

        # Oscillators & volatility
        data["rsi_14"] = compute_rsi(close, period=self.rsi_period)
        macd_df = compute_macd(close)
        data["macd"] = macd_df["macd"]
        data["macd_signal"] = macd_df["macd_signal"]
        data["macd_hist"] = macd_df["macd_hist"]

        data["atr_14"] = compute_atr(data, period=self.atr_period)
        data["atr_pct"] = data["atr_14"] / close.replace(0.0, np.nan)
        data["rolling_vol"] = data["log_ret_1"].rolling(self.vol_window).std()

        # Bollinger-style band position (20-period)
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        upper_20 = sma_20 + (2.0 * std_20)
        lower_20 = sma_20 - (2.0 * std_20)
        band_width = (upper_20 - lower_20).replace(0.0, np.nan)
        data["bb_width"] = band_width / sma_20.replace(0.0, np.nan)
        data["bb_pos"] = (close - lower_20) / band_width

        # Candle body & wick structure
        candle_range = (high - low).replace(0.0, np.nan)
        data["candle_body_pct"] = (close - open_p) / open_p.replace(0.0, np.nan)
        data["upper_wick_ratio"] = (high - np.maximum(open_p, close)) / candle_range
        data["lower_wick_ratio"] = (np.minimum(open_p, close) - low) / candle_range

        # Volume relative to rolling baseline
        vol_sma = volume.rolling(self.vol_window).mean().replace(0.0, np.nan)
        data["vol_ratio"] = volume / vol_sma
        data["vol_delta_pct"] = volume.pct_change(1)

        if include_target:
            future_ret = close.shift(-self.horizon) / close - 1.0
            data["future_ret"] = future_ret
            # Ternary directional target: 1 (long), -1 (short), 0 (flat/noise)
            data["target_signal"] = np.where(
                future_ret > target_threshold,
                1,
                np.where(future_ret < -target_threshold, -1, 0),
            )

        data = data.replace([np.inf, -np.inf], np.nan)
        if self.drop_na:
            data = data.dropna().reset_index(drop=True)

        return data

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Return only numeric model feature columns (excluding raw OHLCV and target columns)."""
        exclude = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "future_ret",
            "target_signal",
        }
        return [
            col
            for col in df.columns
            if col not in exclude and pd.api.types.is_numeric_dtype(df[col])
        ]

    def latest_feature_row(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Return the most recent feature row as a 1-row DataFrame for live inference."""
        feat_df = self.build_features(df, include_target=False)
        if feat_df.empty:
            return None
        cols = self.get_feature_columns(feat_df)
        latest = feat_df.iloc[[-1]][cols].copy()
        return latest.fillna(0.0)