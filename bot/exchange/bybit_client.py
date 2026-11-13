import ccxt

class BybitFuturesClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear'  # Forces USDT-margined linear perpetual contracts
            }
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> list:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_balance(self) -> dict:
        balance = self.exchange.fetch_balance()
        return balance.get('total', {})

    def get_balance(self) -> dict:
        """Alias to support any code calling get_balance()"""
        return self.fetch_balance()

    def fetch_positions(self, symbol: str = None) -> list:
        return self.exchange.fetch_positions([symbol] if symbol else None)

    def set_leverage(self, leverage: int, symbol: str):
        try:
            return self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            print(f"Bybit set_leverage notice: {str(e)}")

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: dict = None):
        return self.exchange.create_order(symbol, order_type, side, amount, price, params or {})

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self.exchange.cancel_order(order_id, symbol)