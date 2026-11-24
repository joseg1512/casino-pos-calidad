from datetime import date

import pytest

from casino_pos.domain.transactions.sale import SaleError, SaleRequest, confirm, quote


def order(**changes) -> SaleRequest:
    values = {
        "customer_name": "Ana",
        "item_name": "Chip",
        "quantity": 2,
        "stock": 10,
        "unit_value": 5,
        "payment_method": "cash",
        "user": "cashier",
    }
    values.update(changes)
    return SaleRequest(**values)


def test_quote_shows_the_amount_before_confirmation():
    quoted = quote(order())
    assert quoted.customer_name == "Ana"
    assert quoted.item_name == "Chip"
    assert quoted.quantity == 2
    assert quoted.amount == 10
    assert quoted.payment_method == "cash"
    assert quoted.user == "cashier"


def test_quote_accepts_card():
    assert quote(order(payment_method="card")).payment_method == "card"


def test_quote_rejects_a_bad_payment_or_price():
    for changes in ({"payment_method": "credit"}, {"unit_value": 0}):
        with pytest.raises(SaleError):
            quote(order(**changes))


def test_quote_rejects_a_quantity_outside_stock():
    for quantity in (0, 11):
        with pytest.raises(SaleError):
            quote(order(quantity=quantity))


def test_confirm_returns_the_receipt_and_the_new_stock():
    receipt, stock = confirm(order(), sold_on=date(2026, 11, 23), number="000001")
    assert receipt.number == "000001"
    assert receipt.sold_on == date(2026, 11, 23)
    assert receipt.customer_name == "Ana"
    assert receipt.detail == "2 Chip"
    assert receipt.amount == 10
    assert receipt.payment_method == "cash"
    assert receipt.user == "cashier"
    assert stock == 8
