from user_service import build_user_record


def test_username_is_trimmed_and_case_normalized():
    assert build_user_record("  Alice  ") == {"username": "alice"}
