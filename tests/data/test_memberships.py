import sqlite3
from datetime import date

import pytest

from casino_pos.data.memberships import (
    MembershipOrder,
    assign_membership,
    list_membership_catalog,
    preview_membership,
    seed_membership_types,
)
from casino_pos.data.sales import SaleOrder, confirm_sale, connect
from casino_pos.domain.memberships.assignment import MembershipError

TODAY = date(2026, 11, 23)


@pytest.fixture
def db():
    connection = connect()
    connection.execute("INSERT INTO customers (id, name, active) VALUES (1, 'Ana', 1)")
    connection.execute("INSERT INTO customers (id, name, active) VALUES (2, 'Luis', 0)")
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (1, 'Chip', 10, 5, 1, 1)"
    )
    connection.commit()
    seed_membership_types(connection)
    yield connection
    connection.close()


def order(**changes) -> MembershipOrder:
    values = {"customer_id": 1, "type_id": 1, "payment_method": "cash", "user": "cashier"}
    values.update(changes)
    return MembershipOrder(**values)


def count(db, table: str) -> int:
    return db.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]


def test_catalog_lists_customers_and_types(db):
    catalog = list_membership_catalog(db)
    assert [row["name"] for row in catalog["customers"]] == ["Ana", "Luis"]
    assert [row["name"] for row in catalog["types"]] == ["Gold", "Platinum", "Silver"]
    assert catalog["types"][2]["active"] == 0


def test_preview_stores_nothing(db):
    quoted = preview_membership(db, order(), assigned_on=TODAY)
    assert quoted.amount == 50
    assert quoted.expires_on == date(2026, 12, 22)
    assert count(db, "memberships") == 0
    assert count(db, "transactions") == 0


def test_preview_uses_today_by_default(db):
    assert preview_membership(db, order()).starts_on == date.today()


def test_assign_stores_the_membership_and_its_payment_together(db):
    receipt = assign_membership(db, order(type_id=2, payment_method="card"), assigned_on=TODAY)
    assert receipt.number == "000001"
    assert receipt.terms.amount == 500
    assert receipt.terms.expires_on == date(2027, 11, 22)
    membership = db.execute("SELECT * FROM memberships").fetchone()
    assert membership["customer_id"] == 1
    assert membership["type_name"] == "Platinum"
    assert membership["starts_on"] == "2026-11-23"
    assert membership["expires_on"] == "2027-11-22"
    assert membership["payment_number"] == "000001"
    payment = db.execute("SELECT * FROM transactions").fetchone()
    assert payment["number"] == "000001"
    assert payment["amount"] == 500
    assert payment["payment_method"] == "card"
    assert payment["user_name"] == "cashier"


def test_receipt_numbers_are_shared_with_chip_sales(db):
    confirm_sale(
        db,
        SaleOrder(customer_id=1, item_id=1, quantity=1, payment_method="cash", user="cashier"),
    )
    first = assign_membership(db, order(), assigned_on=TODAY)
    second = assign_membership(db, order(), assigned_on=TODAY)
    assert (first.number, second.number) == ("000002", "000003")


def test_rejected_assignment_stores_nothing(db):
    for rejected in (
        order(customer_id=2),
        order(customer_id=9),
        order(type_id=3),
        order(type_id=9),
        order(payment_method="credit"),
    ):
        with pytest.raises(MembershipError):
            assign_membership(db, rejected, assigned_on=TODAY)
    assert count(db, "memberships") == 0
    assert count(db, "transactions") == 0


def test_failed_membership_insert_rolls_back_the_payment(db):
    db.execute(
        "CREATE TRIGGER abort_membership BEFORE INSERT ON memberships "
        "BEGIN SELECT RAISE(ABORT, 'fail'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        assign_membership(db, order(), assigned_on=TODAY)
    assert count(db, "memberships") == 0
    assert count(db, "transactions") == 0


def test_failed_payment_insert_stores_no_membership(db):
    db.execute(
        "CREATE TRIGGER abort_payment BEFORE INSERT ON transactions "
        "BEGIN SELECT RAISE(ABORT, 'fail'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        assign_membership(db, order(), assigned_on=TODAY)
    assert count(db, "memberships") == 0
    assert count(db, "transactions") == 0
