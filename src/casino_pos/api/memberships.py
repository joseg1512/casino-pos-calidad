import sqlite3
from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from casino_pos.data.memberships import (
    MembershipOrder,
    assign_membership,
    list_membership_catalog,
    preview_membership,
)
from casino_pos.domain.memberships.assignment import MembershipError, MembershipQuote


class MembershipIn(BaseModel):
    customer_id: int
    type_id: int
    payment_method: str
    user: str


def _order(body: MembershipIn) -> MembershipOrder:
    return MembershipOrder(
        customer_id=body.customer_id,
        type_id=body.type_id,
        payment_method=body.payment_method,
        user=body.user,
    )


def _terms(quoted: MembershipQuote) -> dict:
    payload = asdict(quoted)
    payload["starts_on"] = quoted.starts_on.isoformat()
    payload["expires_on"] = quoted.expires_on.isoformat()
    return payload


def _call(action):
    try:
        return action()
    except MembershipError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def membership_routes(db: Callable[[], sqlite3.Connection]) -> APIRouter:
    router = APIRouter(prefix="/memberships")

    @router.get("/catalog")
    def catalog(current: sqlite3.Connection = Depends(db)):  # noqa: B008
        return list_membership_catalog(current)

    @router.post("/preview")
    def preview(body: MembershipIn, current: sqlite3.Connection = Depends(db)):  # noqa: B008
        return _call(lambda: _terms(preview_membership(current, _order(body))))

    @router.post("")
    def assign(body: MembershipIn, current: sqlite3.Connection = Depends(db)):  # noqa: B008
        def run():
            receipt = assign_membership(current, _order(body))
            return {
                "number": receipt.number,
                "issued_on": receipt.issued_on.isoformat(),
                **_terms(receipt.terms),
            }

        return _call(run)

    return router
