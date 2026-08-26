import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str | None
    api_key: str | None
    model: str
    max_steps: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.getenv("REPOFIX_BASE_URL") or None,
            api_key=os.getenv("REPOFIX_API_KEY") or None,
            model=os.getenv("REPOFIX_MODEL", "gpt-4o-mini"),
            max_steps=int(os.getenv("REPOFIX_MAX_STEPS", "12")),
        )
