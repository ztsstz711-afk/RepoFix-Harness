import pytest

from pagination import page_items


def test_first_page_starts_with_first_item():
    assert page_items(["a", "b", "c", "d"], page=1, page_size=2) == ["a", "b"]


def test_second_page_follows_first_page():
    assert page_items(["a", "b", "c", "d"], page=2, page_size=2) == ["c", "d"]


def test_page_numbers_are_one_based():
    with pytest.raises(ValueError):
        page_items(["a"], page=0, page_size=1)
