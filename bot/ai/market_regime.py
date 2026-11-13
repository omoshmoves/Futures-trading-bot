import pandas as pd
from typing import Dict, Any

class AIMarketAnalyzer:
    @staticmethod
    def analyze_market_regime(df_enriched: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes the latest technical indicators to determine trend direction, 
        market regime, momentum, and volatility.
        """
        if df_enriched.empty or len(df_enriched) < 200:
            return {"status": "insufficient_data"}

        latest = df_enriched.iloc[-1]
        prev = df_enriched.iloc[-2]

        close = latest['close']
        ema_9 = latest['ema_9']
        ema_21 = latest['ema_21']
        ema_50 = latest['ema_50']
        ema_200 = latest['ema_200']
        rsi = latest['rsi']
        adx = latest['adx']
        macd_hist = latest['macd_hist']
        atr = latest['atr']
        stoch_rsi = latest['stoch_rsi']

        # 1. Trend Direction Analysis using EMAs
        if close > ema_50 and ema_50 > ema_200:
            trend = "STRONG_BULLISH"
        elif close < ema_50 and ema_50 < ema_200:
            trend = "STRONG_BEARISH"
        elif close > ema_200:
            trend = "MILD_BULLISH"
        else:
            trend = "MILD_BEARISH"

        # 2. Market Regime Detection (Trend vs Range)
        if adx > 25:
            regime = "TRENDING"
        else:
            regime = "RANGING_OR_CHOPPY"

        # 3. Momentum & Overbought/Oversold Conditions
        if rsi > 70:
            momentum = "OVERBOUGHT"
        elif rsi < 30:
            momentum = "OVERSOLD"
        elif rsi > 50:
            momentum = "BULLISH_MOMENTUM"
        else:
            momentum = "BEARISH_MOMENTUM"

        # 4. Volatility Assessment (using ATR relative to price)
        atr_pct = (atr / close) * 100
        if atr_pct > 1.5:
            volatility = "HIGH"
        elif atr_pct < 0.5:
            volatility = "LOW"
        else:
            volatility = "MODERATE"

        return {
            "timestamp": str(latest['timestamp']),
            "close_price": close,
            "trend_direction": trend,
            "market_regime": regime,
            "momentum": momentum,
            "volatility": volatility,
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "stoch_rsi": round(stoch_rsi, 2),
            "macd_histogram": round(macd_hist, 4),
            "evidence": {
                "price_vs_ema200": "Above" if close > ema_200 else "Below",
                "ema_9_vs_21": "Bullish Crossover" if ema_9 > ema_21 else "Bearish Crossover",
                "atr_percentage": round(atr_pct, 2)
            }
        }