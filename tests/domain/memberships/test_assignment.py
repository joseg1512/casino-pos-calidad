from datetime import date

import pytest

from casino_pos.domain.memberships.assignment import (
    MembershipError,
    MembershipRequest,
    confirm,
    expiry,
    quote,
)

TODAY = date(2026, 11, 23)


def request(**changes) -> MembershipRequest:
    values = {
        "customer_name": "Ana",
        "type_name": "Gold",
        "cost": 50,
        "duration_days": 30,
        "payment_method": "cash",
        "user": "cashier",
    }
    values.update(changes)
    return MembershipRequest(**values)


def test_expiry_counts_the_start_day():
    assert expiry(TODAY, 1) == TODAY
    assert expiry(TODAY, 30) == date(2026, 12, 22)
    assert expiry(date(2028, 2, 1), 29) == date(2028, 2, 29)


def test_expiry_rejects_a_bad_duration():
    for days in (0, -5, 1.5, True):
        with pytest.raises(MembershipError):
            expiry(TODAY, days)


def test_quote_shows_every_field_before_confirmation():
    quoted = quote(request(), assigned_on=TODAY)
    assert quoted.customer_name == "Ana"
    assert quoted.type_name == "Gold"
    assert quoted.starts_on == TODAY
    assert quoted.expires_on == date(2026, 12, 22)
    assert quoted.amount == 50
    assert quoted.payment_method == "cash"
    assert quoted.user == "cashier"


def test_quote_uses_the_type_cost_and_accepts_card_and_free_plans():
    assert quote(request(payment_method="card"), assigned_on=TODAY).payment_method == "card"
    assert quote(request(cost=0), assigned_on=TODAY).amount == 0


def test_quote_rejects_bad_input():
    for changes in (
        {"payment_method": "credit"},
        {"cost": -1},
        {"user": "  "},
        {"duration_days": 0},
    ):
        with pytest.raises(MembershipError):
            quote(request(**changes), assigned_on=TODAY)


def test_confirm_returns_a_receipt_with_the_required_fields():
    receipt = confirm(request(payment_method="card"), assigned_on=TODAY, number="000007")
    assert receipt.number == "000007"
    assert receipt.issued_on == TODAY
    assert receipt.terms.customer_name == "Ana"
    assert receipt.terms.type_name == "Gold"
    assert receipt.terms.starts_on == TODAY
    assert receipt.terms.expires_on == date(2026, 12, 22)
    assert receipt.terms.amount == 50
    assert receipt.terms.payment_method == "card"
    assert receipt.terms.user == "cashier"
