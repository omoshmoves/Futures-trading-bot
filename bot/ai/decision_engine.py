from typing import Dict, Any
import pandas as pd

class TradingDecisionEngine:
    def __init__(self, risk_reward_ratio: float = 2.0, atr_sl_multiplier: float = 1.5):
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier

    def evaluate_trade(self, analysis: dict, df_enriched: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates market state and computes institutional-grade risk-managed trade parameters.
        """
        if analysis.get("status") == "insufficient_data" or df_enriched.empty:
            return {"action": "HOLD", "reason": "Insufficient data for decision"}

        latest = df_enriched.iloc[-1]
        close = latest['close']
        atr = latest['atr']
        trend = analysis.get("trend_direction")
        regime = analysis.get("market_regime")
        adx = analysis.get("adx")

        action = "HOLD"
        reason = "Conditions neutral or fail risk gates."

        # Strict Institutional Risk Gate: Require ADX > 22 for trend continuation trades
        if adx >= 22:
            if "BULLISH" in trend:
                action = "LONG"
                reason = f"Bullish trend alignment with ADX {adx:.1f} (>22)."
            elif "BEARISH" in trend:
                action = "SHORT"
                reason = f"Bearish trend alignment with ADX {adx:.1f} (>22)."

        # Calculate Risk Parameters if a trade is triggered
        setup = {
            "action": action,
            "reason": reason,
            "entry_price": close,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward_ratio": self.risk_reward_ratio
        }

        if action == "LONG":
            sl = close - (atr * self.atr_sl_multiplier)
            tp = close + ((close - sl) * self.risk_reward_ratio)
            setup["stop_loss"] = round(sl, 2)
            setup["take_profit"] = round(tp, 2)
        elif action == "SHORT":
            sl = close + (atr * self.atr_sl_multiplier)
            tp = close - ((sl - close) * self.risk_reward_ratio)
            setup["stop_loss"] = round(sl, 2)
            setup["take_profit"] = round(tp, 2)

        return setup