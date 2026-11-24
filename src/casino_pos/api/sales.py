import sqlite3
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from casino_pos.api.memberships import membership_routes
from casino_pos.data.memberships import seed_membership_types
from casino_pos.data.sales import (
    SaleOrder,
    confirm_sale,
    connect,
    list_catalog,
    preview_sale,
    seed_demo,
)
from casino_pos.domain.transactions.sale import SaleError

PAGE = Path(__file__).with_name("page.html").read_text(encoding="utf-8")


class SaleIn(BaseModel):
    customer_id: int
    item_id: int
    quantity: int
    payment_method: str
    user: str


def _order(body: SaleIn) -> SaleOrder:
    return SaleOrder(
        customer_id=body.customer_id,
        item_id=body.item_id,
        quantity=body.quantity,
        payment_method=body.payment_method,
        user=body.user,
    )


def _call(action):
    try:
        return action()
    except SaleError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def create_app(connection: sqlite3.Connection | None = None) -> FastAPI:
    database = connection if connection is not None else connect()
    application = FastAPI()

    def db() -> sqlite3.Connection:
        return database

    @application.get("/", response_class=HTMLResponse)
    def home():
        return PAGE

    @application.get("/chip-sales/catalog")
    def catalog(current: sqlite3.Connection = Depends(db)):  # noqa: B008
        return list_catalog(current)

    @application.post("/chip-sales/preview")
    def preview(body: SaleIn, current: sqlite3.Connection = Depends(db)):  # noqa: B008
        return _call(lambda: asdict(preview_sale(current, _order(body))))

    @application.post("/chip-sales")
    def sell(body: SaleIn, current: sqlite3.Connection = Depends(db)):  # noqa: B008
        def run():
            receipt = confirm_sale(current, _order(body))
            payload = asdict(receipt)
            payload["sold_on"] = receipt.sold_on.isoformat()
            return payload

        return _call(run)

    application.include_router(membership_routes(db))
    return application


def demo_app() -> FastAPI:
    connection = connect()
    seed_demo(connection)
    seed_membership_types(connection)
    return create_app(connection)
