import ccxt
from typing import Dict, Any, List
from bot.exchange.base import BaseExchange

class BinanceFuturesClient(BaseExchange):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {
                'defaultType': 'future', # Select USDⓈ-M Futures
            },
            'enableRateLimit': True,
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.exchange.fetch_ticker(symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List[Any]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_balance(self) -> Dict[str, Any]:
        return self.exchange.fetch_balance()

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: dict = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        return self.exchange.create_order(symbol, order_type, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return self.exchange.cancel_order(order_id, symbol)

    def fetch_positions(self) -> List[Dict[str, Any]]:
        # Fetch account positions for Binance futures
        balance = self.exchange.fetch_balance()
        return balance.get('info', {}).get('positions', [])

    def set_leverage(self, symbol: str, leverage: int):
        """
        Sets the leverage for a futures symbol.
        Note: CCXT's set_leverage signature is set_leverage(leverage, symbol).
        """
        try:
            return self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            print(f"Warning on set_leverage: {str(e)}")
            # Fallback or pass if already set on testnet
            pass