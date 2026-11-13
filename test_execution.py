import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.execution.order_manager import OrderManager

load_dotenv()

# Initialize Exchange Client (Testnet)
client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)
order_manager = OrderManager(client)

# Mock an approved risk evaluation and trade setup for testing execution logic
mock_trade_setup = {
    "action": "LONG",
    "entry_price": 74000.0,
    "stop_loss": 72800.0,
    "take_profit": 76400.0
}

mock_risk_evaluation = {
    "approved": True,
    "reason": "Passed all institutional risk gates.",
    "position_size": 0.002,  # 0.002 BTC test amount
    "notional_value": 148.0
}

print("Testing OrderManager with mock approved setup...")
result = order_manager.execute_trade("BTC/USDT", mock_risk_evaluation, mock_trade_setup, leverage=2)

print("\n--- Execution Result Report ---")
for key, value in result.items():
    print(f"{key}: {value}")