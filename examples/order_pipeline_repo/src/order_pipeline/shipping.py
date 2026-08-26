from decimal import Decimal


FREE_SHIPPING_THRESHOLD = Decimal("100")


def shipping_fee(merchandise_subtotal: Decimal, destination: str) -> Decimal:
    if merchandise_subtotal >= FREE_SHIPPING_THRESHOLD:
        return Decimal("0")
    if destination == "international":
        return Decimal("20")
    return Decimal("8")
