import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.data.collector import MarketDataCollector
from bot.indicators.technicals import TechnicalIndicatorEngine
from bot.ai.market_regime import AIMarketAnalyzer

load_dotenv()

client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)
collector = MarketDataCollector(client)

symbol = "BTC/USDT"
print(f"Fetching data and running AI Market Analysis for {symbol}...")

# Fetch, enrich, and analyze
df = collector.get_historical_candles(symbol, timeframe='1h', limit=250)
df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)
analysis = AIMarketAnalyzer.analyze_market_regime(df_enriched)

print("\n--- AI Market Intelligence Report ---")
for key, value in analysis.items():
    print(f"{key}: {value}")