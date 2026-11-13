from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseExchange(ABC):
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker information for a trading pair."""
        pass

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List[Any]]:
        """Fetch historical candlestick data."""
        pass

    @abstractmethod
    def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account margin balances."""
        pass

    @abstractmethod
    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: dict = None) -> Dict[str, Any]:
        """Create a market or limit order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an active order."""
        pass

    @abstractmethod
    def fetch_positions(self) -> List[Dict[str, Any]]:
        """Fetch active open futures positions."""
        pass

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a specific trading pair."""
        pass