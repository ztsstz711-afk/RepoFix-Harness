from formatter import normalize_username


def build_user_record(name: str) -> dict[str, str]:
    return {"username": normalize_username(name)}
