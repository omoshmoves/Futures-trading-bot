import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.data.collector import MarketDataCollector
from bot.indicators.technicals import TechnicalIndicatorEngine
from bot.ai.market_regime import AIMarketAnalyzer
from bot.ai.decision_engine import TradingDecisionEngine

load_dotenv()

client = BinanceFuturesClient(
    api_key=os.getenv("BINANCE_API_KEY", ""),
    api_secret=os.getenv("BINANCE_API_SECRET", ""),
    testnet=True
)
collector = MarketDataCollector(client)
decision_engine = TradingDecisionEngine()

symbol = "BTC/USDT"
print(f"Running full pipeline for {symbol}...")

# 1. Collect -> 2. Enrich -> 3. Analyze Regime -> 4. Evaluate Trade Decision
df = collector.get_historical_candles(symbol, timeframe='1h', limit=250)
df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)
analysis = AIMarketAnalyzer.analyze_market_regime(df_enriched)
trade_decision = decision_engine.evaluate_trade(analysis, df_enriched)

print("\n--- Autonomous Trading Decision & Risk Setup ---")
for key, value in trade_decision.items():
    print(f"{key}: {value}")