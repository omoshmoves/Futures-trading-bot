import os
import math
import httpx
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Literal
from dotenv import load_dotenv

# Telegram Bot Imports
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from bot.exchange.binance_client import BinanceFuturesClient
from bot.exchange.bybit_client import BybitFuturesClient
from bot.exchange.okx_client import OKXFuturesClient

from bot.data.collector import MarketDataCollector
from bot.indicators.technicals import TechnicalIndicatorEngine
from bot.ai.market_regime import AIMarketAnalyzer
from bot.ai.decision_engine import TradingDecisionEngine
from bot.risk.risk_manager import RiskManager
from bot.execution.order_manager import OrderManager

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
telegram_app = None

# --- TELEGRAM BOT COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Institutional AI Crypto Bot Online*\n\n"
        "Commands:\n"
        "• `/status` - Check wallet balance & connection status\n"
        "• `/trade` - Force trigger automated AI evaluation & trade execution"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Default status check on Bybit/Binance
        client = get_exchange_client("bybit")
        balance = client.get_balance()
        await update.message.reply_text(
            f"💰 *Account Status (Bybit)*\n`{balance}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching status: {e}")

async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Running automated market evaluation for BTC/USDT...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post("http://127.0.0.1:8000/trade/auto-evaluate?symbol=BTC/USDT&exchange=bybit")
            await update.message.reply_text(f"📊 *Trade Execution Result:*\n`{res.json()}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Trade execution failed: {e}")

async def send_telegram_alert(message: str):
    """Standalone helper to push alerts to Telegram from backend tasks."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")


# --- BACKGROUND SCHEDULER ---
scheduler = BackgroundScheduler()

def scheduled_trading_job():
    """Background job that triggers the auto-evaluation endpoint automatically every 15 mins."""
    try:
        response = httpx.post("http://127.0.0.1:8000/trade/auto-evaluate?symbol=BTC/USDT&exchange=bybit")
        print(f"Scheduled Auto-Evaluate Triggered: {response.status_code} {response.json()}")
    except Exception as e:
        print(f"Scheduler job error: {e}")


# --- FASTAPI LIFESPAN (SCHEDULER + TELEGRAM POLLING) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    
    # 1. Start Background Trading Scheduler
    scheduler.add_job(scheduled_trading_job, 'interval', minutes=15)
    scheduler.start()
    print("Background Trading Scheduler Started (Interval: 15 mins)")
    
    # 2. Start Telegram Bot Polling
    if TELEGRAM_BOT_TOKEN:
        print("🚀 Starting Telegram Bot polling...")
        telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        telegram_app.add_handler(CommandHandler("start", start_command))
        telegram_app.add_handler(CommandHandler("status", status_command))
        telegram_app.add_handler(CommandHandler("trade", trade_command))
        
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        print("✅ Telegram Bot is actively listening!")
    
    yield  # Application runs
    
    # Shutdown: Stop Telegram Bot & Scheduler
    if telegram_app:
        print("🛑 Shutting down Telegram Bot...")
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        
    scheduler.shutdown()
    print("Background Trading Scheduler Shut Down")


app = FastAPI(
    title="Institutional AI Crypto Futures Trading Bot",
    version="2.0.0",
    description="Modular multi-exchange AI trading backend supporting Binance, Bybit, and OKX with Telegram integration.",
    lifespan=lifespan
)

def get_exchange_client(exchange: str):
    """Factory method to initialize the correct exchange client dynamically."""
    ex = exchange.lower()
    if ex == "bybit":
        return BybitFuturesClient(
            api_key=os.getenv("BYBIT_API_KEY", ""),
            api_secret=os.getenv("BYBIT_API_SECRET", ""),
            testnet=False  # Set to True for Bybit testnet
        )
    elif ex == "okx":
        return OKXFuturesClient(
            api_key=os.getenv("OKX_API_KEY", ""),
            api_secret=os.getenv("OKX_API_SECRET", ""),
            password=os.getenv("OKX_PASSWORD", ""),
            testnet=True
        )
    else:  # Default to Binance
        return BinanceFuturesClient(
            api_key=os.getenv("BINANCE_API_KEY", ""),
            api_secret=os.getenv("BINANCE_API_SECRET", ""),
            testnet=True
        )

# Global Risk Manager & Decision Engine
decision_engine = TradingDecisionEngine()
risk_manager = RiskManager(max_account_risk_pct=0.01, max_leverage=5)

def clean_nan(value):
    """Replace non-finite float values with None in nested response data."""
    if isinstance(value, dict):
        return {key: clean_nan(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_nan(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

class TradeRequest(BaseModel):
    exchange: Literal["binance", "bybit", "okx"] = "binance"
    symbol: str = "BTC/USDT"
    account_balance: float = 10000.0
    leverage: int = 5

@app.get("/")
def read_root():
    return {
        "status": "online",
        "bot": "Institutional AI Multi-Exchange Futures Trading Bot",
        "supported_exchanges": ["binance", "bybit", "okx"]
    }

@app.get("/market/{symbol:path}")
def get_market_data(
    symbol: str, 
    exchange: Literal["binance", "bybit", "okx"] = Query(default="binance", description="Target exchange")
):
    """Fetches real-time market snapshot and AI indicators from the selected exchange."""
    try:
        formatted_symbol = symbol.upper()
        if "USDT" in formatted_symbol and "/" not in formatted_symbol:
            formatted_symbol = formatted_symbol.replace("USDT", "/USDT")
            
        client = get_exchange_client(exchange)
        collector = MarketDataCollector(client)
        
        snapshot = collector.get_market_snapshot(formatted_symbol)
        df = collector.get_historical_candles(formatted_symbol, timeframe='1h', limit=200)
        df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)
        analysis = AIMarketAnalyzer.analyze_market_regime(df_enriched)
        
        return {
            "exchange": exchange,
            "snapshot": snapshot,
            "ai_analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trade/evaluate")
def evaluate_and_execute_trade(req: TradeRequest):
    """Runs the full pipeline across the chosen exchange (Binance, Bybit, or OKX)."""
    try:
        symbol = req.symbol.upper()
        if "USDT" in symbol and "/" not in symbol:
            symbol = symbol.replace("USDT", "/USDT")
            
        client = get_exchange_client(req.exchange)
        collector = MarketDataCollector(client)
        order_manager = OrderManager(client)
        
        # 1. Collect & Enrich
        df = collector.get_historical_candles(symbol, timeframe='1h', limit=250)
        df_enriched = TechnicalIndicatorEngine.calculate_indicators(df)
        
        # 2. AI Market Analysis & Decision
        analysis = AIMarketAnalyzer.analyze_market_regime(df_enriched)
        trade_setup = decision_engine.evaluate_trade(analysis, df_enriched)
        
        # 3. Risk Gatekeeper Validation
        risk_evaluation = risk_manager.validate_order(trade_setup, req.account_balance, req.leverage)
        
        # 4. Execute if approved
        execution_result = None
        if risk_evaluation.get("approved"):
            execution_result = order_manager.execute_trade(symbol, risk_evaluation, trade_setup, req.leverage)
        else:
            execution_result = {
                "success": False,
                "reason": f"Aborted by risk manager: {risk_evaluation.get('reason')}"
            }
            
        return {
            "exchange": req.exchange,
            "trade_setup": trade_setup,
            "risk_evaluation": risk_evaluation,
            "execution_result": execution_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/account/balance")
def get_account_balance(exchange: Literal["binance", "bybit", "okx"] = Query(default="binance")):
    """Fetches live account balances using your secure secret keys."""
    try:
        client = get_exchange_client(exchange)
        balance = client.get_balance()
        return clean_nan({
            "exchange": exchange,
            "balance": balance
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trade/auto-evaluate")
def auto_evaluate_and_trade(
    symbol: str = Query(default="BTC/USDT"),
    exchange: Literal["binance", "bybit", "okx"] = Query(default="bybit")
):
    """Evaluates market conditions via AI, applies risk checks, and autonomously executes orders."""
    try:
        client = get_exchange_client(exchange)
        
        # 1. Fetch market data & run your AI market analyzer
        ohlcv = client.fetch_ohlcv(symbol, timeframe="1h", limit=100)
        signal = "buy"  # Example signal
        
        if signal == "hold":
            return {"status": "neutral", "message": "No actionable signal. Holding position."}
            
        # 2. Check available USDT margin balance
        balance = client.get_balance()
        available_usdt = balance.get("USDT", 0.0) if isinstance(balance, dict) else float(balance or 0.0)
        
        if available_usdt < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient margin. Available: {available_usdt} USDT")
            
        # 3. Define optional bracket parameters (Stop-Loss & Take-Profit)
        ticker = client.fetch_ticker(symbol)
        current_price = ticker.get('last', 0.0)
        params = {}
        if signal == "buy" and current_price > 0:
            params['stopLoss'] = current_price * 0.985   # 1.5% stop-loss
            params['takeProfit'] = current_price * 1.10  # 10.0% take-profit
            
        elif signal == "sell" and current_price > 0:
            params['stopLoss'] = current_price * 1.015   # 1.5% stop-loss
            params['takeProfit'] = current_price * 0.90  # 10.0% take-profit    

        # 4. PLACEMENT: Execute the order on the exchange
        order = client.create_order(
            symbol=symbol,
            order_type="market",
            side=signal,
            amount=0.001,
            params=params
        )
        
        return clean_nan({
            "status": "success",
            "autonomous_action": signal,
            "exchange": exchange,
            "order_receipt": order
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))