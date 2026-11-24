from datetime import date, timedelta

from fastapi.testclient import TestClient

from casino_pos.api.sales import create_app, demo_app
from casino_pos.data.memberships import seed_membership_types
from casino_pos.data.sales import connect

MEMBERSHIP = {"customer_id": 1, "type_id": 1, "payment_method": "cash", "user": "cashier"}


def seeded():
    connection = connect()
    connection.execute("INSERT INTO customers (id, name, active) VALUES (1, 'Ana', 1)")
    connection.execute("INSERT INTO customers (id, name, active) VALUES (2, 'Luis', 0)")
    connection.commit()
    seed_membership_types(connection)
    return connection


def count(connection, table: str) -> int:
    return connection.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]


def test_preview_shows_every_field_and_stores_nothing():
    connection = seeded()
    client = TestClient(create_app(connection))
    response = client.post("/memberships/preview", json=MEMBERSHIP)
    assert response.status_code == 200
    body = response.json()
    today = date.today()
    assert body == {
        "customer_name": "Ana",
        "type_name": "Gold",
        "starts_on": today.isoformat(),
        "expires_on": (today + timedelta(days=29)).isoformat(),
        "amount": 50,
        "payment_method": "cash",
        "user": "cashier",
    }
    assert count(connection, "memberships") == 0
    assert count(connection, "transactions") == 0
    connection.close()


def test_confirm_returns_the_receipt_and_stores_both_records():
    connection = seeded()
    client = TestClient(create_app(connection))
    response = client.post("/memberships", json=MEMBERSHIP | {"payment_method": "card"})
    assert response.status_code == 200
    body = response.json()
    assert body["number"] == "000001"
    assert body["issued_on"] == date.today().isoformat()
    assert body["customer_name"] == "Ana"
    assert body["type_name"] == "Gold"
    assert body["amount"] == 50
    assert body["payment_method"] == "card"
    assert body["user"] == "cashier"
    assert count(connection, "memberships") == 1
    assert count(connection, "transactions") == 1
    connection.close()


def test_confirm_rejects_an_inactive_customer_or_type():
    connection = seeded()
    client = TestClient(create_app(connection))
    for changes in ({"customer_id": 2}, {"type_id": 3}, {"payment_method": "credit"}):
        response = client.post("/memberships", json=MEMBERSHIP | changes)
        assert response.status_code == 400
    assert count(connection, "memberships") == 0
    assert count(connection, "transactions") == 0
    connection.close()


def test_demo_catalog_and_page_include_memberships():
    client = TestClient(demo_app())
    assert 'id="m-type"' in client.get("/").text
    catalog = client.get("/memberships/catalog").json()
    assert catalog["customers"][0]["name"] == "Ana"
    assert [row["name"] for row in catalog["types"]] == ["Gold", "Platinum", "Silver"]
