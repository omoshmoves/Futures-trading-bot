import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.data.collector import MarketDataCollector

load_dotenv()

# Initialize Exchange Client and Data Collector
client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)
collector = MarketDataCollector(client)

symbol = "BTC/USDT"
print(f"Fetching market snapshot for {symbol}...")
snapshot = collector.get_market_snapshot(symbol)
print(snapshot)

print(f"\nFetching last 5 OHLCV candles (1-hour timeframe) for {symbol}...")
df_candles = collector.get_historical_candles(symbol, timeframe='1h', limit=5)
print(df_candles)