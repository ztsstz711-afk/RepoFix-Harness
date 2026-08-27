def display_name(profile: dict) -> str:
    """Return a normalized display name for a user profile."""
    return profile["name"].strip().title()
