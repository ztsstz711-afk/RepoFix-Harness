def has_enough_stock(available: int, requested: int) -> bool:
    if requested < 1:
        return False
    return available > requested
