from decimal import Decimal

from order_pipeline.shipping import shipping_fee


def test_domestic_shipping_below_threshold():
    assert shipping_fee(Decimal("99.99"), "domestic") == Decimal("8")


def test_shipping_is_free_at_threshold():
    assert shipping_fee(Decimal("100"), "international") == Decimal("0")


def test_international_shipping_below_threshold():
    assert shipping_fee(Decimal("40"), "international") == Decimal("20")
