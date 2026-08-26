from dataclasses import dataclass
from decimal import Decimal

from .discounts import loyalty_discount
from .models import Order
from .pricing import merchandise_subtotal
from .shipping import shipping_fee


@dataclass(frozen=True)
class Quote:
    merchandise: Decimal
    shipping: Decimal
    discount: Decimal
    total: Decimal


def quote_order(order: Order) -> Quote:
    merchandise = merchandise_subtotal(order.lines)
    shipping = shipping_fee(merchandise, order.destination)
    discount = loyalty_discount(merchandise + shipping, order.customer_tier)
    return Quote(
        merchandise=merchandise,
        shipping=shipping,
        discount=discount,
        total=merchandise + shipping - discount,
    )
