import pytest

from inventory.service import create_order


def test_exact_stock_can_fulfill_order():
    assert create_order("keyboard", 2, {"keyboard": 2}) == {
        "sku": "keyboard",
        "quantity": 2,
    }


def test_insufficient_stock_is_rejected():
    with pytest.raises(ValueError, match="insufficient"):
        create_order("keyboard", 3, {"keyboard": 2})


def test_non_positive_quantity_is_rejected():
    with pytest.raises(ValueError, match="insufficient"):
        create_order("keyboard", 0, {"keyboard": 2})
