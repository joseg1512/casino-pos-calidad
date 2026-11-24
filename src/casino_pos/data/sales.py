import sqlite3
from dataclasses import dataclass
from datetime import date

from casino_pos.domain.transactions.sale import SaleError, SaleQuote, SaleRequest, confirm, quote

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    stock INTEGER NOT NULL,
    unit_value INTEGER NOT NULL,
    active INTEGER NOT NULL,
    sellable INTEGER NOT NULL
);
CREATE TABLE transactions (
    number TEXT PRIMARY KEY,
    sold_on TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    detail TEXT NOT NULL,
    amount INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    user_name TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class SaleOrder:
    customer_id: int
    item_id: int
    quantity: int
    payment_method: str
    user: str


def seed_demo(connection) -> None:
    connection.execute("INSERT INTO customers (id, name, active) VALUES (1, 'Ana', 1)")
    connection.execute("INSERT INTO customers (id, name, active) VALUES (2, 'Luis', 0)")
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (1, 'Chip', 10, 5, 1, 1)"
    )
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (2, 'Dice', 4, 2, 1, 0)"
    )
    connection.commit()


def list_catalog(connection) -> dict:
    customers = connection.execute(
        "SELECT id, name, active FROM customers ORDER BY id"
    ).fetchall()
    items = connection.execute(
        "SELECT id, name, stock, unit_value, active, sellable FROM items ORDER BY id"
    ).fetchall()
    return {
        "customers": [dict(row) for row in customers],
        "items": [dict(row) for row in items],
    }


def connect() -> sqlite3.Connection:
    # shortcut: one in-memory connection, shared with the request thread
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _row(connection, sql: str, key: int, missing: str):
    row = connection.execute(sql, (key,)).fetchone()
    if row is None:
        raise SaleError(missing)
    return row


def _request(connection, order: SaleOrder) -> SaleRequest:
    customer = _row(
        connection,
        "SELECT name, active FROM customers WHERE id = ?",
        order.customer_id,
        "customer was not found",
    )
    if not customer["active"]:
        raise SaleError("customer is not active")
    item = _row(
        connection,
        "SELECT name, stock, unit_value, active, sellable FROM items WHERE id = ?",
        order.item_id,
        "item was not found",
    )
    if not item["active"] or not item["sellable"]:
        raise SaleError("item is not sellable")
    return SaleRequest(
        customer_name=customer["name"],
        item_name=item["name"],
        quantity=order.quantity,
        stock=item["stock"],
        unit_value=item["unit_value"],
        payment_method=order.payment_method,
        user=order.user,
    )


def preview_sale(connection, order: SaleOrder) -> SaleQuote:
    return quote(_request(connection, order))


def confirm_sale(connection, order: SaleOrder, *, sold_on: date | None = None):
    sold_on = sold_on or date.today()
    with connection:
        request = _request(connection, order)
        count = connection.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"]
        receipt, stock = confirm(request, sold_on=sold_on, number=f"{count + 1:06d}")
        connection.execute("UPDATE items SET stock = ? WHERE id = ?", (stock, order.item_id))
        connection.execute(
            """
            INSERT INTO transactions (
                number, sold_on, customer_name, detail, amount, payment_method, user_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.number,
                receipt.sold_on.isoformat(),
                receipt.customer_name,
                receipt.detail,
                receipt.amount,
                receipt.payment_method,
                receipt.user,
            ),
        )
    return receipt
