from dataclasses import dataclass
from datetime import date

from casino_pos.domain.memberships.assignment import (
    MembershipError,
    MembershipQuote,
    MembershipReceipt,
    MembershipRequest,
    confirm,
    quote,
)

MEMBERSHIP_SCHEMA = """
CREATE TABLE membership_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    cost INTEGER NOT NULL CHECK (cost >= 0),
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    active INTEGER NOT NULL
);
CREATE TABLE memberships (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    type_id INTEGER NOT NULL REFERENCES membership_types (id),
    type_name TEXT NOT NULL,
    starts_on TEXT NOT NULL,
    expires_on TEXT NOT NULL,
    amount INTEGER NOT NULL,
    payment_number TEXT NOT NULL UNIQUE REFERENCES transactions (number)
);
"""


@dataclass(frozen=True)
class MembershipOrder:
    customer_id: int
    type_id: int
    payment_method: str
    user: str


def seed_membership_types(connection) -> None:
    connection.execute(
        "INSERT INTO membership_types (id, name, description, cost, duration_days, active) "
        "VALUES (1, 'Gold', 'Monthly access', 50, 30, 1)"
    )
    connection.execute(
        "INSERT INTO membership_types (id, name, description, cost, duration_days, active) "
        "VALUES (2, 'Platinum', 'Yearly access', 500, 365, 1)"
    )
    connection.execute(
        "INSERT INTO membership_types (id, name, description, cost, duration_days, active) "
        "VALUES (3, 'Silver', 'Retired plan', 20, 30, 0)"
    )
    connection.commit()


def list_membership_catalog(connection) -> dict:
    customers = connection.execute(
        "SELECT id, name, active FROM customers ORDER BY id"
    ).fetchall()
    types = connection.execute(
        "SELECT id, name, description, cost, duration_days, active "
        "FROM membership_types ORDER BY id"
    ).fetchall()
    return {
        "customers": [dict(row) for row in customers],
        "types": [dict(row) for row in types],
    }


def _row(connection, sql: str, key: int, missing: str):
    row = connection.execute(sql, (key,)).fetchone()
    if row is None:
        raise MembershipError(missing)
    return row


def _request(connection, order: MembershipOrder) -> MembershipRequest:
    customer = _row(
        connection,
        "SELECT name, active FROM customers WHERE id = ?",
        order.customer_id,
        "customer was not found",
    )
    if not customer["active"]:
        raise MembershipError("customer is not active")
    kind = _row(
        connection,
        "SELECT name, cost, duration_days, active FROM membership_types WHERE id = ?",
        order.type_id,
        "membership type was not found",
    )
    if not kind["active"]:
        raise MembershipError("membership type is not active")
    return MembershipRequest(
        customer_name=customer["name"],
        type_name=kind["name"],
        cost=kind["cost"],
        duration_days=kind["duration_days"],
        payment_method=order.payment_method,
        user=order.user,
    )


def preview_membership(
    connection, order: MembershipOrder, *, assigned_on: date | None = None
) -> MembershipQuote:
    return quote(_request(connection, order), assigned_on=assigned_on or date.today())


def _next_number(connection) -> str:
    count = connection.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"]
    return f"{count + 1:06d}"


def assign_membership(
    connection, order: MembershipOrder, *, assigned_on: date | None = None
) -> MembershipReceipt:
    assigned_on = assigned_on or date.today()
    with connection:
        receipt = confirm(
            _request(connection, order),
            assigned_on=assigned_on,
            number=_next_number(connection),
        )
        terms = receipt.terms
        connection.execute(
            """
            INSERT INTO transactions (
                number, sold_on, customer_name, detail, amount, payment_method, user_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.number,
                receipt.issued_on.isoformat(),
                terms.customer_name,
                f"{terms.type_name} ({terms.starts_on} / {terms.expires_on})",
                terms.amount,
                terms.payment_method,
                terms.user,
            ),
        )
        connection.execute(
            """
            INSERT INTO memberships (
                customer_id, type_id, type_name, starts_on, expires_on, amount, payment_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.customer_id,
                order.type_id,
                terms.type_name,
                terms.starts_on.isoformat(),
                terms.expires_on.isoformat(),
                terms.amount,
                receipt.number,
            ),
        )
    return receipt
