import pandas as pd
from typing import List, Dict, Any
from bot.exchange.base import BaseExchange

class MarketDataCollector:
    def __init__(self, exchange_client: BaseExchange):
        self.exchange = exchange_client

    def get_historical_candles(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """
        Fetches OHLCV candlestick data from the exchange and returns a structured pandas DataFrame.
        Columns: timestamp, open, high, low, close, volume
        """
        raw_candles = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        
        df = pd.DataFrame(raw_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Convert timestamp to readable datetime format
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Ensure numerical types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        return df

    def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Gathers a comprehensive snapshot including current ticker price and 24h stats.
        """
        ticker = self.exchange.fetch_ticker(symbol)
        return {
            'symbol': symbol,
            'last_price': ticker.get('last'),
            'high_24h': ticker.get('high'),
            'low_24h': ticker.get('low'),
            'volume_24h': ticker.get('baseVolume'),
            'timestamp': ticker.get('timestamp')
        }