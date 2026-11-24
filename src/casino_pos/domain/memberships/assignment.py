from dataclasses import dataclass
from datetime import date, timedelta

PAYMENT_METHODS = {"cash", "card"}


class MembershipError(ValueError):
    pass


@dataclass(frozen=True)
class MembershipRequest:
    customer_name: str
    type_name: str
    cost: int
    duration_days: int
    payment_method: str
    user: str


@dataclass(frozen=True)
class MembershipQuote:
    customer_name: str
    type_name: str
    starts_on: date
    expires_on: date
    amount: int
    payment_method: str
    user: str


@dataclass(frozen=True)
class MembershipReceipt:
    number: str
    issued_on: date
    terms: MembershipQuote


def expiry(starts_on: date, duration_days: int) -> date:
    # the expiry day is still valid (HU-08), so a 30-day plan covers day 1 to day 30
    if isinstance(duration_days, bool) or not isinstance(duration_days, int):
        raise MembershipError("duration must be a whole number of days above zero")
    if duration_days <= 0:
        raise MembershipError("duration must be a whole number of days above zero")
    return starts_on + timedelta(days=duration_days - 1)


def _checked(request: MembershipRequest, assigned_on: date) -> date:
    if request.payment_method not in PAYMENT_METHODS:
        raise MembershipError("payment method must be cash or card")
    if request.cost < 0:
        raise MembershipError("membership cost cannot be negative")
    if not request.user.strip():
        raise MembershipError("user is required")
    return expiry(assigned_on, request.duration_days)


def quote(request: MembershipRequest, *, assigned_on: date) -> MembershipQuote:
    expires_on = _checked(request, assigned_on)
    return MembershipQuote(
        customer_name=request.customer_name,
        type_name=request.type_name,
        starts_on=assigned_on,
        expires_on=expires_on,
        amount=request.cost,
        payment_method=request.payment_method,
        user=request.user,
    )


def confirm(request: MembershipRequest, *, assigned_on: date, number: str) -> MembershipReceipt:
    return MembershipReceipt(
        number=number,
        issued_on=assigned_on,
        terms=quote(request, assigned_on=assigned_on),
    )
