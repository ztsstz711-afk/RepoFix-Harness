from repofix.text import compact_text


def test_compact_text_never_exceeds_limit():
    for limit in range(0, 80):
        result, omitted = compact_text("x" * 200, limit)
        assert len(result) <= limit
        assert omitted >= 0
