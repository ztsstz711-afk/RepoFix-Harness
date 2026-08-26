def page_items(items: list, page: int, page_size: int) -> list:
    """Return one-based pages from a sequence."""
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    start = page * page_size
    return items[start : start + page_size]
