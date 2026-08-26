from decimal import Decimal

from .models import OrderLine


def merchandise_subtotal(lines: tuple[OrderLine, ...]) -> Decimal:
    return sum((line.unit_price * line.quantity for line in lines), start=Decimal("0"))
