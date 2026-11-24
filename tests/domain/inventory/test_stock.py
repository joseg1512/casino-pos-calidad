import pytest

from casino_pos.domain.inventory.stock import StockError, issue


def test_issue_decreases_stock():
    assert issue(10, 4) == 6


def test_issue_rejects_a_quantity_outside_stock():
    for quantity in (0, -1, 11, True):
        with pytest.raises(StockError):
            issue(10, quantity)
