from decimal import Decimal


DISCOUNT_RATES = {
    "standard": Decimal("0"),
    "silver": Decimal("0.05"),
    "gold": Decimal("0.10"),
}


def loyalty_discount(eligible_amount: Decimal, customer_tier: str) -> Decimal:
    rate = DISCOUNT_RATES.get(customer_tier, Decimal("0"))
    return (eligible_amount * rate).quantize(Decimal("0.01"))
