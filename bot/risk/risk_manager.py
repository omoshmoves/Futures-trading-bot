from typing import Dict, Any

class RiskManager:
    def __init__(self, max_account_risk_pct: float = 0.01, max_leverage: int = 10):
        self.max_account_risk_pct = max_account_risk_pct  # e.g., 1% risk per trade
        self.max_leverage = max_leverage

    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculates exact position size in base currency (e.g., BTC amount) 
        such that if the stop loss is hit, exactly max_account_risk_pct of equity is lost.
        """
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit == 0:
            return 0.0

        allowed_dollar_risk = account_balance * self.max_account_risk_pct
        position_size = allowed_dollar_risk / risk_per_unit
        
        return position_size

    def validate_order(self, trade_setup: dict, account_balance: float, current_leverage: int) -> Dict[str, Any]:
        """
        Validates the trade setup against hard risk gates before execution.
        """
        if trade_setup.get("action") == "HOLD":
            return {"approved": False, "reason": "Trade setup is HOLD."}

        if current_leverage > self.max_leverage:
            return {"approved": False, "reason": f"Leverage {current_leverage}x exceeds max allowed {self.max_leverage}x."}

        entry = trade_setup.get("entry_price")
        sl = trade_setup.get("stop_loss")
        
        if not entry or not sl:
            return {"approved": False, "reason": "Missing entry or stop loss price."}

        # Calculate position size
        size = self.calculate_position_size(account_balance, entry, sl)
        position_notional_value = size * entry
        max_allowed_notional = account_balance * self.max_leverage

        if position_notional_value > max_allowed_notional:
            return {"approved": False, "reason": "Position notional value exceeds maximum leverage bounds."}

        return {
            "approved": True,
            "reason": "Passed all institutional risk gates.",
            "position_size": round(size, 6),
            "notional_value": round(position_notional_value, 2)
        }