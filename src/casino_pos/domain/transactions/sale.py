from dataclasses import dataclass
from datetime import date

from casino_pos.domain.inventory.stock import StockError, issue


class SaleError(ValueError):
    pass


@dataclass(frozen=True)
class SaleRequest:
    customer_name: str
    item_name: str
    quantity: int
    stock: int
    unit_value: int
    payment_method: str
    user: str


@dataclass(frozen=True)
class SaleQuote:
    customer_name: str
    item_name: str
    quantity: int
    amount: int
    payment_method: str
    user: str


@dataclass(frozen=True)
class Receipt:
    number: str
    sold_on: date
    customer_name: str
    detail: str
    amount: int
    payment_method: str
    user: str


def _checked(request: SaleRequest) -> int:
    if request.payment_method not in {"cash", "card"}:
        raise SaleError("payment method must be cash or card")
    if request.unit_value <= 0:
        raise SaleError("item is not sellable")
    try:
        return issue(request.stock, request.quantity)
    except StockError as error:
        raise SaleError(str(error)) from error


def quote(request: SaleRequest) -> SaleQuote:
    _checked(request)
    return SaleQuote(
        customer_name=request.customer_name,
        item_name=request.item_name,
        quantity=request.quantity,
        amount=request.quantity * request.unit_value,
        payment_method=request.payment_method,
        user=request.user,
    )


def confirm(request: SaleRequest, *, sold_on: date, number: str) -> tuple[Receipt, int]:
    new_stock = _checked(request)
    return (
        Receipt(
            number=number,
            sold_on=sold_on,
            customer_name=request.customer_name,
            detail=f"{request.quantity} {request.item_name}",
            amount=request.quantity * request.unit_value,
            payment_method=request.payment_method,
            user=request.user,
        ),
        new_stock,
    )
