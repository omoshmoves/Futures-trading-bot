import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from importlib import import_module

    FeatureEngineer = import_module(".feature_eng", package=__package__).FeatureEngineer
    PerformanceTracker = import_module(".performance", package=__package__).PerformanceTracker
    streamer_module = import_module(".streamer", package=__package__)
    MarketStreamer = streamer_module.MarketStreamer
    SUPPORTED_EXCHANGES = streamer_module.SUPPORTED_EXCHANGES
    SignalTrainer = import_module(".trainer", package=__package__).SignalTrainer
except ImportError:
    # Allow the module to run when the bot directory is on PYTHONPATH directly.
    FeatureEngineer = import_module("feature_eng").FeatureEngineer
    PerformanceTracker = import_module("performance").PerformanceTracker
    streamer_module = import_module("streamer")
    MarketStreamer = streamer_module.MarketStreamer
    SUPPORTED_EXCHANGES = streamer_module.SUPPORTED_EXCHANGES
    SignalTrainer = import_module("trainer").SignalTrainer

logger = logging.getLogger(__name__)


class TradingCore:
    """Clean orchestrator for multi-exchange futures data, signals, orders, and performance."""

    def __init__(
        self,
        exchanges: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        timeframe: str = "15m",
        candle_limit: int = 200,
        order_size: float = 0.01,
        leverage: int = 1,
        dry_run: bool = True,
        use_testnet: bool = False,
        initial_equity: float = 1000.0,
    ) -> None:
        self.exchanges = [
            ex.lower() for ex in (exchanges or SUPPORTED_EXCHANGES) if ex.lower() in SUPPORTED_EXCHANGES
        ]
        self.symbols = symbols or ["BTC/USDT:USDT"]
        self.timeframe = timeframe
        self.candle_limit = candle_limit
        self.order_size = float(order_size)
        self.leverage = int(leverage)
        self.dry_run = bool(dry_run)
        self._lock = threading.Lock()

        self.streamer = MarketStreamer(exchanges=self.exchanges, use_testnet=use_testnet)
        self.feature_engineer = FeatureEngineer()
        self.trainer = SignalTrainer(feature_engineer=self.feature_engineer)
        self.performance = PerformanceTracker(initial_equity=initial_equity)

        self.paused = False
        self.cycle_count = 0
        self.last_run_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self.latest_prices: Dict[str, float] = {}
        self.last_signals: Dict[str, Dict[str, Any]] = {}

    def train_model(
        self,
        exchange_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Train and persist the signal model using recent candles."""
        ex = (exchange_id or (self.exchanges[0] if self.exchanges else "binance")).lower()
        sym = symbol or self.symbols[0]
        df = self.streamer.fetch_ohlcv_df(ex, symbol=sym, timeframe=self.timeframe, limit=limit)
        return self.trainer.train(df, save_model=True)

    def _execute_order(
        self,
        ex_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False,
    ) -> tuple[float, float]:
        """Execute a paper or live futures order and return (fill_price, fill_size)."""
        if self.dry_run:
            return price, amount

        client = self.streamer.clients[ex_id]
        ccxt_side = "buy" if side == "long" else "sell"

        if not reduce_only and self.leverage > 1 and hasattr(client, "set_leverage"):
            try:
                client.set_leverage(self.leverage, symbol)
            except Exception as exc:
                logger.warning("Leverage setup skipped on %s %s: %s", ex_id, symbol, exc)

        params = {"reduceOnly": True} if reduce_only else {}
        order = client.create_order(
            symbol=symbol,
            type="market",
            side=ccxt_side,
            amount=amount,
            price=None,
            params=params,
        )
        fill_price = float(order.get("average") or order.get("price") or price)
        fill_size = float(order.get("filled") or order.get("amount") or amount)
        return fill_price, fill_size

    def _step_pair(self, ex_id: str, symbol: str) -> Dict[str, Any]:
        """Run a single evaluation/execution step for one exchange and symbol."""
        pos_key = f"{ex_id}::{symbol.upper()}"
        df = self.streamer.fetch_ohlcv_df(ex_id, symbol=symbol, timeframe=self.timeframe, limit=self.candle_limit)
        if df.empty:
            return {"exchange": ex_id, "symbol": symbol, "action": "no_data"}

        price = float(df["close"].iloc[-1])
        self.latest_prices[pos_key] = price

        pred = self.trainer.predict_latest(df)
        signal = int(pred.get("signal", 0))
        desired_side = "long" if signal == 1 else ("short" if signal == -1 else None)

        open_pos = self.performance.open_positions.get(pos_key)
        action = "hold"

        if open_pos and desired_side and open_pos["side"] != desired_side:
            self._execute_order(ex_id, symbol, desired_side, float(open_pos["size"]), price, reduce_only=True)
            self.performance.close_position(ex_id, symbol, exit_price=price)
            action = f"closed_{open_pos['side']}"
            open_pos = None

        if open_pos is None and desired_side is not None:
            fill_price, fill_size = self._execute_order(ex_id, symbol, desired_side, self.order_size, price)
            self.performance.open_position(
                exchange=ex_id,
                symbol=symbol,
                side=desired_side,
                entry_price=fill_price,
                size=fill_size,
                metadata={"signal": signal, "confidence": pred.get("confidence", 0.0)},
            )
            action = f"opened_{desired_side}"

        snapshot = {
            "exchange": ex_id,
            "symbol": symbol,
            "price": price,
            "signal": signal,
            "confidence": pred.get("confidence", 0.0),
            "action": action,
            "dry_run": self.dry_run,
        }
        self.last_signals[pos_key] = snapshot
        return snapshot

    def run_cycle(self) -> Dict[str, Any]:
        """Run one full cycle across all configured exchanges and symbols."""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            if self.paused:
                return {"status": "paused", "timestamp": now, "cycle_count": self.cycle_count}

            self.cycle_count += 1
            self.last_run_at = now
            results: List[Dict[str, Any]] = []
            errors: List[Dict[str, str]] = []

            for ex_id in self.exchanges:
                for symbol in self.symbols:
                    try:
                        results.append(self._step_pair(ex_id, symbol))
                    except Exception as exc:
                        logger.error("Cycle error (%s %s): %s", ex_id, symbol, exc)
                        errors.append({"pair": f"{ex_id}::{symbol}", "error": str(exc)})

            self.last_error = errors[-1]["error"] if errors else None
            return {
                "status": "ok" if not errors else "partial_error",
                "timestamp": now,
                "cycle_count": self.cycle_count,
                "results": results,
                "errors": errors,
            }

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def get_status(self) -> Dict[str, Any]:
        """Return current bot state, signals, and performance summary."""
        return {
            "paused": self.paused,
            "dry_run": self.dry_run,
            "exchanges": self.exchanges,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "cycle_count": self.cycle_count,
            "last_run_at": self.last_run_at,
            "last_error": self.last_error,
            "model_loaded": self.trainer.model is not None,
            "last_signals": self.last_signals,
            "performance": self.performance.get_summary(mark_prices=self.latest_prices),
        }

    def shutdown(self) -> None:
        """Persist state and close exchange clients."""
        self.performance.save()
        self.streamer.close()