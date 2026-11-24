class StockError(ValueError):
    pass


def issue(stock: int, quantity: int) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise StockError("quantity must be from 1 up to the stock")
    if quantity <= 0 or quantity > stock:
        raise StockError("quantity must be from 1 up to the stock")
    return stock - quantity
