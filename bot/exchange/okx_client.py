import ccxt
from bot.exchange.base import BaseExchange

class OKXFuturesClient(BaseExchange):
    def __init__(self, api_key: str, api_secret: str, password: str, testnet: bool = True):
        self.exchange = ccxt.okx({
            'apiKey': api_key,
            'secret': api_secret,
            'password': password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> list:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def fetch_positions(self, symbol: str = None) -> list:
        return self.exchange.fetch_positions([symbol] if symbol else None)

    def set_leverage(self, leverage: int, symbol: str):
        try:
            return self.exchange.set_leverage(leverage, symbol, 'cross')
        except Exception as e:
            print(f"OKX set_leverage notice: {str(e)}")

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: dict = None):
        return self.exchange.create_order(symbol, order_type, side, amount, price, params or {})

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self.exchange.cancel_order(order_id, symbol)