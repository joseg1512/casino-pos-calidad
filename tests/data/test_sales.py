import sqlite3

import pytest

from casino_pos.data.sales import SaleOrder, confirm_sale, connect, preview_sale
from casino_pos.domain.transactions.sale import SaleError


@pytest.fixture
def db():
    connection = connect()
    connection.execute("INSERT INTO customers (id, name, active) VALUES (1, 'Ana', 1)")
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (1, 'Chip', 10, 5, 1, 1)"
    )
    connection.execute("INSERT INTO customers (id, name, active) VALUES (2, 'Inactive', 0)")
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (2, 'Old chip', 4, 5, 0, 1)"
    )
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (3, 'Cards', 4, 5, 1, 0)"
    )
    connection.commit()
    yield connection
    connection.close()


def order(**changes) -> SaleOrder:
    values = {
        "customer_id": 1,
        "item_id": 1,
        "quantity": 2,
        "payment_method": "cash",
        "user": "cashier",
    }
    values.update(changes)
    return SaleOrder(**values)


def test_preview_does_not_store_a_sale(db):
    quoted = preview_sale(db, order())
    assert quoted.amount == 10
    assert db.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"] == 0
    assert db.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"] == 10


def test_confirm_stores_the_receipt_and_decreases_stock(db):
    receipt = confirm_sale(db, order(payment_method="card"))
    assert receipt.number == "000001"
    assert receipt.detail == "2 Chip"
    assert receipt.amount == 10
    assert receipt.payment_method == "card"
    assert receipt.user == "cashier"
    assert db.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"] == 8
    assert db.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"] == 1


def test_confirm_uses_today_when_no_date_is_given(db):
    receipt = confirm_sale(db, order())
    assert receipt.sold_on.isoformat() == db.execute(
        "SELECT sold_on FROM transactions"
    ).fetchone()["sold_on"]


def test_rejected_sale_leaves_stock_unchanged(db):
    for sale in (
        order(customer_id=2),
        order(customer_id=9),
        order(item_id=2),
        order(item_id=3),
        order(item_id=9),
        order(quantity=11),
    ):
        with pytest.raises(SaleError):
            confirm_sale(db, sale)
    assert db.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"] == 10
    assert db.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"] == 0


def test_failed_insert_rolls_back_the_stock_update(db):
    db.execute(
        "CREATE TRIGGER abort_sale BEFORE INSERT ON transactions "
        "BEGIN SELECT RAISE(ABORT, 'fail'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        confirm_sale(db, order())
    assert db.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"] == 10
    assert db.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"] == 0
