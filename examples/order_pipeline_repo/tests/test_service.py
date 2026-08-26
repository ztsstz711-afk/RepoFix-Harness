from decimal import Decimal

from order_pipeline import Order, OrderLine, quote_order


def order(amount: str, tier: str = "standard", destination: str = "domestic") -> Order:
    return Order((OrderLine(Decimal(amount), 1),), tier, destination)


def test_standard_customer_pays_shipping_without_discount():
    quote = quote_order(order("50"))
    assert quote.total == Decimal("58")
    assert quote.discount == Decimal("0.00")


def test_gold_discount_applies_only_to_merchandise_not_shipping():
    quote = quote_order(order("50", tier="gold"))
    assert quote.merchandise == Decimal("50")
    assert quote.shipping == Decimal("8")
    assert quote.discount == Decimal("5.00")
    assert quote.total == Decimal("53.00")


def test_gold_customer_keeps_free_shipping_behavior():
    quote = quote_order(order("100", tier="gold", destination="international"))
    assert quote.shipping == Decimal("0")
    assert quote.discount == Decimal("10.00")
    assert quote.total == Decimal("90.00")
