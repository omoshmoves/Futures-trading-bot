import numpy as np
import pandas as pd

class TechnicalIndicatorEngine:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a DataFrame with columns [timestamp, open, high, low, close, volume]
        and returns the DataFrame enriched with all technical indicators.
        """
        df = df.copy()

        # 1. Exponential Moving Averages (EMAs)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. Relative Strength Index (RSI - 14 period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 3. MACD (Moving Average Convergence Divergence)
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 4. Bollinger Bands (20 period, 2 std dev)
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        # 5. Average True Range (ATR - 14 period)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()

        # 6. Volume Weighted Average Price (VWAP)
        v = df['volume']
        p = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (p * v).cumsum() / v.cumsum()

        # 7. Average Directional Index (ADX - 14 period)
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        
        tr14 = true_range.rolling(window=14).sum()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / tr14)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / tr14)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.rolling(window=14).mean()

        # 8. Stochastic RSI (14 period)
        rsi_min = df['rsi'].rolling(window=14).min()
        rsi_max = df['rsi'].rolling(window=14).max()
        df['stoch_rsi'] = (df['rsi'] - rsi_min) / (rsi_max - rsi_min)

        return df