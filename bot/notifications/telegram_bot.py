import os
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
API_BASE_URL = "http://127.0.0.1:8000"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responds to /start."""
    await update.message.reply_text(
        "🤖 **Bybit Autonomous Bot Online**\n\n"
        "Commands:\n"
        "• `/status` - Check wallet balance & open positions\n"
        "• `/trade` - Force trigger AI market evaluation"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches balance from FastAPI backend."""
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{API_BASE_URL}/account/balance?exchange=bybit")
            if res.status_code == 200:
                data = res.json()
                await update.message.reply_text(f"💰 **Account Status:**\n`{data}`", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"⚠️ Error fetching status: {res.text}")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to reach backend: {e}")

async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers the evaluation endpoint manually."""
    await update.message.reply_text("🔄 Evaluating market signal for BTC/USDT...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(f"{API_BASE_URL}/trade/auto-evaluate?symbol=BTC/USDT&exchange=bybit")
            await update.message.reply_text(f"📊 **Trade Result:**\n`{res.json()}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Trade execution failed: {e}")

async def send_telegram_alert(message: str):
    """Standalone helper function to push alerts to Telegram from anywhere in your backend."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        from telegram import Update
from telegram.ext import ContextTypes

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Bybit Autonomous Bot Online**\n\n"
        "Available Commands:\n"
        "• `/status` - Check wallet balance & open positions\n"
        "• `/trade` - Force trigger AI market evaluation"
    )