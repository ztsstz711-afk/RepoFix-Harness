from config_loader import merge_config


def test_explicit_override_wins():
    assert merge_config({"timeout": 10}) == {"timeout": 10, "retries": 3}


def test_none_override_keeps_default():
    assert merge_config({"timeout": None}) == {"timeout": 30, "retries": 3}
