import os
import time
import logging
from typing import Dict, List, Optional

import ccxt
import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_EXCHANGES = ("binance", "bybit", "okx")


class MarketStreamer:
    """Fetches OHLCV candles and live futures ticker data across Binance, Bybit, and OKX."""

    def __init__(
        self,
        exchanges: Optional[List[str]] = None,
        use_testnet: bool = False,
        retries: int = 3,
        retry_delay: float = 1.5,
    ) -> None:
        self.selected_exchanges = [
            ex.lower() for ex in (exchanges or SUPPORTED_EXCHANGES) if ex.lower() in SUPPORTED_EXCHANGES
        ]
        self.use_testnet = use_testnet
        self.retries = retries
        self.retry_delay = retry_delay
        self.clients: Dict[str, ccxt.Exchange] = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize CCXT futures (swap) clients using environment variables."""
        env_map = {
            "binance": ("BINANCE_API_KEY", "BINANCE_API_SECRET"),
            "bybit": ("BYBIT_API_KEY", "BYBIT_API_SECRET"),
            "okx": ("OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSPHRASE"),
        }

        for ex_id in self.selected_exchanges:
            keys = env_map[ex_id]
            api_key = os.getenv(keys[0], "").strip()
            secret = os.getenv(keys[1], "").strip()
            passphrase = os.getenv(keys[2], "").strip() if len(keys) > 2 else ""

            params = {
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",  # Perpetual futures across Binance, Bybit, OKX
                },
            }
            if api_key and secret:
                params["apiKey"] = api_key
                params["secret"] = secret
            if passphrase:
                params["password"] = passphrase

            exchange_class = getattr(ccxt, ex_id)
            client = exchange_class(params)

            if self.use_testnet and hasattr(client, "set_sandbox_mode"):
                try:
                    client.set_sandbox_mode(True)
                except Exception as exc:
                    logger.warning("Could not enable sandbox mode for %s: %s", ex_id, exc)

            self.clients[ex_id] = client
            logger.info("Initialized %s futures client (auth=%s)", ex_id, bool(api_key and secret))

    def _run_with_retry(self, func, *args, **kwargs):
        """Execute a CCXT call with simple retry backoff."""
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as exc:
                last_exc = exc
                logger.warning("Transient error (%s) on attempt %d/%d: %s", type(exc).__name__, attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(self.retry_delay * attempt)
            except ccxt.ExchangeError as exc:
                logger.error("Exchange error: %s", exc)
                raise
        raise RuntimeError(f"Failed after {self.retries} retries: {last_exc}") from last_exc

    def fetch_ohlcv_df(
        self,
        exchange_id: str,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "15m",
        limit: int = 200,
    ) -> pd.DataFrame:
        """Fetch historical/latest OHLCV candles and return a clean DataFrame."""
        ex_id = exchange_id.lower()
        if ex_id not in self.clients:
            raise ValueError(f"Unsupported or uninitialized exchange: {exchange_id}")

        client = self.clients[ex_id]
        raw = self._run_with_retry(client.fetch_ohlcv, symbol, timeframe=timeframe, limit=limit)

        if not raw:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_ticker(self, exchange_id: str, symbol: str = "BTC/USDT:USDT") -> Dict[str, Optional[float]]:
        """Fetch latest market price, bid/ask, and 24h quote volume."""
        ex_id = exchange_id.lower()
        if ex_id not in self.clients:
            raise ValueError(f"Unsupported or uninitialized exchange: {exchange_id}")

        client = self.clients[ex_id]
        ticker = self._run_with_retry(client.fetch_ticker, symbol)
        return {
            "exchange": ex_id,
            "symbol": symbol,
            "last": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "volume_24h": ticker.get("quoteVolume") or ticker.get("baseVolume"),
            "timestamp": ticker.get("timestamp"),
        }

    def fetch_multi_exchange_candles(
        self,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "15m",
        limit: int = 200,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV DataFrames across all active exchanges without letting one failure break all."""
        results: Dict[str, pd.DataFrame] = {}
        for ex_id in self.clients:
            try:
                results[ex_id] = self.fetch_ohlcv_df(ex_id, symbol=symbol, timeframe=timeframe, limit=limit)
            except Exception as exc:
                logger.error("Failed fetching OHLCV from %s for %s: %s", ex_id, symbol, exc)
        return results

    def close(self) -> None:
        """Close open exchange sessions cleanly if supported."""
        for ex_id, client in self.clients.items():
            if hasattr(client, "close"):
                try:
                    client.close()
                except Exception as exc:
                    logger.warning("Error closing client %s: %s", ex_id, exc)