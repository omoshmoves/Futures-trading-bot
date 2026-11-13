import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.data.collector import MarketDataCollector
from bot.indicators.technicals import TechnicalIndicatorEngine

load_dotenv()

client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)
collector = MarketDataCollector(client)

# Fetch 200 candles (required for 200 EMA calculation)
print("Fetching 200 candles for BTC/USDT...")
df = collector.get_historical_candles("BTC/USDT", timeframe='1h', limit=200)

# Calculate indicators
print("Calculating technical indicators...")
df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)

# Display the latest row of computed indicators
latest = df_enriched.iloc[-1]
print("\n--- Latest Technical Indicators for BTC/USDT ---")
print(f"Timestamp: {latest['timestamp']}")
print(f"Close Price: {latest['close']:.2f}")
print(f"RSI (14): {latest['rsi']:.2f}")
print(f"MACD: {latest['macd']:.4f} | Signal: {latest['macd_signal']:.4f}")
print(f"EMA 9: {latest['ema_9']:.2f} | EMA 200: {latest['ema_200']:.2f}")
print(f"Bollinger Upper: {latest['bb_upper']:.2f} | Lower: {latest['bb_lower']:.2f}")
print(f"ATR (14): {latest['atr']:.2f}")
print(f"VWAP: {latest['vwap']:.2f}")
print(f"ADX: {latest['adx']:.2f}")
print(f"Stochastic RSI: {latest['stoch_rsi']:.2f}")