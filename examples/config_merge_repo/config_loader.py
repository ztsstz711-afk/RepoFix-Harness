DEFAULT_CONFIG = {
    "timeout": 30,
    "retries": 3,
}


def merge_config(overrides: dict) -> dict:
    """Apply meaningful user overrides on top of defaults."""
    return {**DEFAULT_CONFIG, **overrides}
