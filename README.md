# Institutional AI Crypto Futures Trading Bot

An institutional-grade, modular, and autonomous algorithmic cryptocurrency futures trading platform designed for Binance Futures (Testnet/Live). Features real-time multi-indicator analysis, strict risk gates, ATR-based position sizing, and a high-performance FastAPI management backend.

## Architecture Modules
* **`exchange/`**: CCXT-powered exchange connectors (`BinanceFuturesClient`).
* **`data/`**: Real-time ticker and historical OHLCV data collectors (`MarketDataCollector`).
* **`indicators/`**: Pandas/NumPy technical indicator calculation engine (RSI, MACD, EMAs, Bollinger Bands, ATR, VWAP, ADX, Stochastic RSI).
* **`ai/`**: Market regime classification and rule-based trade decision engines.
* **`risk/`**: Equity risk firewall and position-sizing calculator.
* **`execution/`**: Order management and state reconciliation handlers.
* **`api/`**: FastAPI web service exposing monitoring and execution endpoints.

## Quick Start
1. Install dependencies:
   ```powershell
   pip install -r requirements.txt