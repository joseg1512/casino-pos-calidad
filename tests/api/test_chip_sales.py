from fastapi.testclient import TestClient

from casino_pos.api.sales import create_app
from casino_pos.data.sales import connect

SALE = {
    "customer_id": 1,
    "item_id": 1,
    "quantity": 2,
    "payment_method": "cash",
    "user": "cashier",
}


def seeded():
    connection = connect()
    connection.execute("INSERT INTO customers (id, name, active) VALUES (1, 'Ana', 1)")
    connection.execute(
        "INSERT INTO items (id, name, stock, unit_value, active, sellable) "
        "VALUES (1, 'Chip', 10, 5, 1, 1)"
    )
    connection.commit()
    return connection


def test_preview_shows_the_sale_and_stores_nothing():
    connection = seeded()
    client = TestClient(create_app(connection))
    response = client.post("/chip-sales/preview", json=SALE)
    assert response.status_code == 200
    assert response.json()["amount"] == 10
    assert response.json()["user"] == "cashier"
    total = connection.execute("SELECT COUNT(*) AS total FROM transactions").fetchone()["total"]
    assert total == 0
    connection.close()


def test_confirm_stores_the_sale():
    connection = seeded()
    client = TestClient(create_app(connection))
    response = client.post("/chip-sales", json=SALE)
    assert response.status_code == 200
    body = response.json()
    assert body["number"] == "000001"
    assert body["detail"] == "2 Chip"
    assert body["amount"] == 10
    stock = connection.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"]
    assert stock == 8
    connection.close()


def test_confirm_rejects_a_quantity_above_stock():
    connection = seeded()
    client = TestClient(create_app(connection))
    response = client.post("/chip-sales", json=SALE | {"quantity": 11})
    assert response.status_code == 400
    stock = connection.execute("SELECT stock FROM items WHERE id = 1").fetchone()["stock"]
    assert stock == 10
    connection.close()


def test_default_database_has_no_customers():
    client = TestClient(create_app())
    response = client.post("/chip-sales/preview", json=SALE)
    assert response.status_code == 400
