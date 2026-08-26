from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OrderLine:
    unit_price: Decimal
    quantity: int


@dataclass(frozen=True)
class Order:
    lines: tuple[OrderLine, ...]
    customer_tier: str = "standard"
    destination: str = "domestic"
