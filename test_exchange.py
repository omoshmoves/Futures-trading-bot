import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient

load_dotenv()

# Initialize client (uses testnet/sandbox mode by default)
client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)

try:
    print("Fetching BTC/USDT Ticker from Binance Futures...")
    ticker = client.fetch_ticker("BTC/USDT")
    print(f"Success! Current BTC Price: {ticker.get('last')}")
except Exception as e:
    print(f"Connection test note (expected if API keys are blank for paper trading): {e}")