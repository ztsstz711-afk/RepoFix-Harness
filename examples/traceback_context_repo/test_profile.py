from profile import display_name


def test_display_name_normalizes_present_name():
    assert display_name({"name": "  ada lovelace  "}) == "Ada Lovelace"


def test_display_name_uses_anonymous_for_missing_name():
    assert display_name({}) == "Anonymous"
