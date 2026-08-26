import json
from dataclasses import asdict

from .schemas import Action


class RepeatedActionGuard:
    """Stop exact action loops while resetting after a real file change."""

    def __init__(self, max_identical_actions: int = 2):
        if max_identical_actions < 1:
            raise ValueError("max_identical_actions must be positive")
        self.max_identical_actions = max_identical_actions

    def reason(self, history: list[dict], action: Action) -> str | None:
        if action.name == "finish":
            return None
        fingerprint = self._fingerprint(asdict(action))
        matches = 0
        for event in reversed(history):
            observation = event.get("observation", {})
            if (
                event.get("action", {}).get("name") == "apply_patch"
                and observation.get("metadata", {}).get("changed")
            ):
                break
            previous = event.get("action")
            if previous and self._fingerprint(previous) == fingerprint:
                matches += 1
        if matches >= self.max_identical_actions:
            return (
                f"action repeated {matches + 1} times without a file change: "
                f"{action.name}"
            )
        return None

    @staticmethod
    def _fingerprint(action: dict) -> str:
        relevant = {"name": action.get("name"), "arguments": action.get("arguments", {})}
        return json.dumps(relevant, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
