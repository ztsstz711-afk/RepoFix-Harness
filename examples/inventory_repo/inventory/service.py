from .policy import has_enough_stock


def create_order(sku: str, requested: int, stock: dict[str, int]) -> dict:
    available = stock.get(sku, 0)
    if not has_enough_stock(available, requested):
        raise ValueError("insufficient stock")
    return {"sku": sku, "quantity": requested}
