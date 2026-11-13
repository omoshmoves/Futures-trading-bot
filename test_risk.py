import os
from dotenv import load_dotenv
from bot.exchange.binance_client import BinanceFuturesClient
from bot.data.collector import MarketDataCollector
from bot.indicators.technicals import TechnicalIndicatorEngine
from bot.ai.market_regime import AIMarketAnalyzer
from bot.ai.decision_engine import TradingDecisionEngine
from bot.risk.risk_manager import RiskManager

load_dotenv()

client = BinanceFuturesClient(api_key="", api_secret="", testnet=True)
collector = MarketDataCollector(client)
decision_engine = TradingDecisionEngine()
risk_manager = RiskManager(max_account_risk_pct=0.01, max_leverage=5)

symbol = "BTC/USDT"
print(f"Testing Risk Manager gatekeeper for {symbol}...")

# Run pipeline
df = collector.get_historical_candles(symbol, timeframe='1h', limit=250)
df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)
analysis = AIMarketAnalyzer.analyze_market_regime(df_enriched)
trade_setup = decision_engine.evaluate_trade(analysis, df_enriched)

# Simulate account equity of $10,000 USD
mock_account_balance = 10000.0
mock_leverage = 3

risk_evaluation = risk_manager.validate_order(trade_setup, mock_account_balance, mock_leverage)

print("\n--- Risk Gatekeeper Evaluation Report ---")
print(f"Trade Action: {trade_setup.get('action')}")
print(f"Risk Approval: {risk_evaluation.get('approved')}")
print(f"Reason: {risk_evaluation.get('reason')}")
if risk_evaluation.get('approved'):
    print(f"Calculated Position Size: {risk_evaluation.get('position_size')} BTC")
    print(f"Position Notional Value: ${risk_evaluation.get('notional_value')}")