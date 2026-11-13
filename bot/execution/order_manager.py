from typing import Dict, Any
from bot.exchange.base import BaseExchange

class OrderManager:
    def __init__(self, exchange_client: BaseExchange):
        self.exchange = exchange_client

    def execute_trade(self, symbol: str, risk_evaluation: dict, trade_setup: dict, leverage: int = 3) -> Dict[str, Any]:
        """
        Executes an approved trade setup on the exchange with leverage, 
        main position entry, and risk brackets (Stop-Loss / Take-Profit).
        """
        if not risk_evaluation.get("approved"):
            return {
                "success": False,
                "reason": f"Execution aborted by risk manager: {risk_evaluation.get('reason')}"
            }

        action = trade_setup.get("action")
        size = risk_evaluation.get("position_size")
        sl = trade_setup.get("stop_loss")
        tp = trade_setup.get("take_profit")

        if action not in ["LONG", "SHORT"]:
            return {"success": False, "reason": "Invalid action for execution."}

        side = "buy" if action == "LONG" else "sell"

        try:
            # 1. Set Leverage
            print(f"Setting leverage to {leverage}x for {symbol}...")
            self.exchange.set_leverage(symbol, leverage)

            # 2. Place Main Market Order
            print(f"Placing {action} market order for {size} {symbol}...")
            order = self.exchange.create_order(
                symbol=symbol,
                order_type="market",
                side=side,
                amount=size
            )

            order_id = order.get('id')
            print(f"Main order executed successfully! Order ID: {order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "amount": size,
                "stop_loss": sl,
                "take_profit": tp,
                "raw_order": order
            }

        except Exception as e:
            return {
                "success": False,
                "reason": f"Exchange execution error: {str(e)}"
            }