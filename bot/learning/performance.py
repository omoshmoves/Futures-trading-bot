import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks futures trades, realized/unrealized PnL, fees, win rate, and max drawdown."""

    def __init__(
        self,
        initial_equity: float = 1000.0,
        log_path: str = "logs/trade_history.json",
    ) -> None:
        self.initial_equity = float(initial_equity)
        self.log_path = Path(log_path)
        self.trades: List[Dict[str, Any]] = []
        self.open_positions: Dict[str, Dict[str, Any]] = {}

        if self.log_path.exists():
            self.load()

    @staticmethod
    def _position_key(exchange: str, symbol: str) -> str:
        return f"{exchange.lower()}::{symbol.upper()}"

    def open_position(
        self,
        exchange: str,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        fee: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an opened futures position ('long' or 'short')."""
        side_norm = side.lower()
        if side_norm not in ("long", "short"):
            raise ValueError(f"Invalid side '{side}'. Expected 'long' or 'short'.")

        key = self._position_key(exchange, symbol)
        position = {
            "key": key,
            "exchange": exchange.lower(),
            "symbol": symbol.upper(),
            "side": side_norm,
            "entry_price": float(entry_price),
            "size": float(size),
            "entry_fee": float(fee),
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.open_positions[key] = position
        self.save()
        logger.info("Opened %s %s on %s @ %s (size=%s)", side_norm, symbol, exchange, entry_price, size)
        return position

    def close_position(
        self,
        exchange: str,
        symbol: str,
        exit_price: float,
        exit_fee: float = 0.0,
        size: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Close an open position (full or partial), calculate net PnL, and log the trade."""
        key = self._position_key(exchange, symbol)
        pos = self.open_positions.get(key)
        if not pos:
            logger.warning("No open position found for %s", key)
            return None

        close_size = float(size) if size is not None else float(pos["size"])
        close_size = min(close_size, float(pos["size"]))
        if close_size <= 0:
            return None

        fraction = close_size / float(pos["size"]) if float(pos["size"]) > 0 else 1.0
        allocated_entry_fee = float(pos["entry_fee"]) * fraction

        entry_price = float(pos["entry_price"])
        exit_price = float(exit_price)

        if pos["side"] == "long":
            gross_pnl = (exit_price - entry_price) * close_size
        else:
            gross_pnl = (entry_price - exit_price) * close_size

        total_fees = allocated_entry_fee + float(exit_fee)
        net_pnl = gross_pnl - total_fees
        notional = entry_price * close_size
        pnl_pct = (net_pnl / notional * 100.0) if notional > 0 else 0.0

        trade_record = {
            "exchange": pos["exchange"],
            "symbol": pos["symbol"],
            "side": pos["side"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": close_size,
            "gross_pnl": round(gross_pnl, 6),
            "fees": round(total_fees, 6),
            "net_pnl": round(net_pnl, 6),
            "pnl_pct": round(pnl_pct, 4),
            "opened_at": pos["opened_at"],
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.trades.append(trade_record)

        remaining_size = round(float(pos["size"]) - close_size, 10)
        if remaining_size <= 0:
            del self.open_positions[key]
        else:
            pos["size"] = remaining_size
            pos["entry_fee"] = max(0.0, float(pos["entry_fee"]) - allocated_entry_fee)

        self.save()
        logger.info("Closed %s %s on %s | Net PnL: %s", pos["side"], symbol, exchange, trade_record["net_pnl"])
        return trade_record

    def record_closed_trade(
        self,
        exchange: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
        fee: float = 0.0,
    ) -> Dict[str, Any]:
        """Directly log an already-completed trade without needing a prior open_position call."""
        side_norm = side.lower()
        if side_norm == "long":
            gross_pnl = (float(exit_price) - float(entry_price)) * float(size)
        elif side_norm == "short":
            gross_pnl = (float(entry_price) - float(exit_price)) * float(size)
        else:
            raise ValueError(f"Invalid side '{side}'. Expected 'long' or 'short'.")

        net_pnl = gross_pnl - float(fee)
        notional = float(entry_price) * float(size)
        pnl_pct = (net_pnl / notional * 100.0) if notional > 0 else 0.0

        record = {
            "exchange": exchange.lower(),
            "symbol": symbol.upper(),
            "side": side_norm,
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "size": float(size),
            "gross_pnl": round(gross_pnl, 6),
            "fees": round(float(fee), 6),
            "net_pnl": round(net_pnl, 6),
            "pnl_pct": round(pnl_pct, 4),
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.trades.append(record)
        self.save()
        return record

    def compute_unrealized_pnl(self, mark_prices: Dict[str, float]) -> float:
        """Compute total unrealized PnL given { 'binance::BTC/USDT:USDT': 92000.0 }."""
        unrealized = 0.0
        for key, pos in self.open_positions.items():
            mark = mark_prices.get(key)
            if mark is None:
                continue
            mark_val = float(mark)
            entry = float(pos["entry_price"])
            size = float(pos["size"])
            if pos["side"] == "long":
                unrealized += (mark_val - entry) * size
            else:
                unrealized += (entry - mark_val) * size
        return round(unrealized, 6)

    def _max_drawdown(self, equity_curve: List[float]) -> Dict[str, float]:
        """Compute peak-to-trough max drawdown in absolute terms and percentage."""
        if not equity_curve:
            return {"max_drawdown_abs": 0.0, "max_drawdown_pct": 0.0}

        peak = equity_curve[0]
        max_dd_abs = 0.0
        max_dd_pct = 0.0

        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd_abs = peak - eq
            dd_pct = (dd_abs / peak * 100.0) if peak > 0 else 0.0
            if dd_abs > max_dd_abs:
                max_dd_abs = dd_abs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return {
            "max_drawdown_abs": round(max_dd_abs, 6),
            "max_drawdown_pct": round(max_dd_pct, 4),
        }

    def get_summary(self, mark_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Return overall and per-exchange performance metrics."""
        realized_pnl = sum(float(t.get("net_pnl", 0.0)) for t in self.trades)
        total_fees = sum(float(t.get("fees", 0.0)) for t in self.trades)
        unrealized_pnl = self.compute_unrealized_pnl(mark_prices or {})

        wins = [t for t in self.trades if float(t.get("net_pnl", 0.0)) > 0]
        losses = [t for t in self.trades if float(t.get("net_pnl", 0.0)) < 0]

        gross_profit = sum(float(t["net_pnl"]) for t in wins)
        gross_loss = abs(sum(float(t["net_pnl"]) for t in losses))
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0.0
        )

        total_closed = len(self.trades)
        win_rate = round((len(wins) / total_closed) * 100.0, 2) if total_closed > 0 else 0.0

        equity = self.initial_equity
        equity_curve = [equity]
        for t in self.trades:
            equity += float(t.get("net_pnl", 0.0))
            equity_curve.append(equity)

        dd = self._max_drawdown(equity_curve)

        by_exchange: Dict[str, Dict[str, Any]] = {}
        for t in self.trades:
            ex = t.get("exchange", "unknown")
            bucket = by_exchange.setdefault(ex, {"trades": 0, "wins": 0, "net_pnl": 0.0, "fees": 0.0})
            bucket["trades"] += 1
            if float(t.get("net_pnl", 0.0)) > 0:
                bucket["wins"] += 1
            bucket["net_pnl"] = round(bucket["net_pnl"] + float(t.get("net_pnl", 0.0)), 6)
            bucket["fees"] = round(bucket["fees"] + float(t.get("fees", 0.0)), 6)

        for ex, bucket in by_exchange.items():
            bucket["win_rate"] = round((bucket["wins"] / bucket["trades"]) * 100.0, 2) if bucket["trades"] else 0.0

        return {
            "initial_equity": self.initial_equity,
            "current_equity": round(equity + unrealized_pnl, 6),
            "realized_pnl": round(realized_pnl, 6),
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": round(realized_pnl + unrealized_pnl, 6),
            "total_fees": round(total_fees, 6),
            "total_trades": total_closed,
            "open_positions_count": len(self.open_positions),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_abs": dd["max_drawdown_abs"],
            "max_drawdown_pct": dd["max_drawdown_pct"],
            "by_exchange": by_exchange,
        }

    def save(self) -> None:
        """Persist open positions and closed trades to disk."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "initial_equity": self.initial_equity,
            "open_positions": self.open_positions,
            "trades": self.trades,
        }
        with self.log_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self) -> None:
        """Load persisted open positions and closed trades from disk."""
        if not self.log_path.exists():
            return
        with self.log_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        self.initial_equity = float(payload.get("initial_equity", self.initial_equity))
        self.open_positions = payload.get("open_positions", {})
        self.trades = payload.get("trades", [])