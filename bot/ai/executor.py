def execute_ai_trade(client, symbol: str, signal: str, amount: float = 0.001):
    """Handles order placement and automated stop-loss/take-profit brackets."""
    ticker = client.fetch_ticker(symbol)
    current_price = ticker.get('last', 0.0)

    params = {}
    if signal == "buy" and current_price > 0:
        params['stopLoss'] = current_price * 0.985   # 1.5% stop-loss
        params['takeProfit'] = current_price * 1.10  # 10.0% take-profit
    elif signal == "sell" and current_price > 0:
        params['stopLoss'] = current_price * 1.015   # 1.5% stop-loss
        params['takeProfit'] = current_price * 0.90  # 10.0% take-profit

    return client.create_order(
        symbol=symbol,
        order_type="market",
        side=signal,
        amount=amount,
        params=params
    )