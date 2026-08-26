from decimal import Decimal

from order_pipeline.models import OrderLine
from order_pipeline.pricing import merchandise_subtotal


def test_subtotal_accounts_for_quantity():
    lines = (OrderLine(Decimal("12.50"), 2), OrderLine(Decimal("5"), 1))
    assert merchandise_subtotal(lines) == Decimal("30.00")
