import json


class ContextBuilder:
    """Build a bounded prompt from the task and the most recent agent events."""

    def __init__(self, repo: str, task: str, max_chars: int = 24_000, max_observation_chars: int = 6_000):
        self.repo = repo
        self.task = task
        self.max_chars = max_chars
        self.max_observation_chars = max_observation_chars

    def build(self, history: list[dict]) -> str:
        header = (
            f"Repository: {self.repo}\n"
            f"Task: {self.task}\n"
            "Continue from the recent trace below. Inspect before editing and verify with pytest."
        )
        budget = max(self.max_chars - len(header) - 100, 0)
        selected: list[str] = []
        used = 0

        for event in reversed(history):
            compact = self._compact_event(event)
            if used + len(compact) > budget:
                break
            selected.append(compact)
            used += len(compact)

        selected.reverse()
        omitted = len(history) - len(selected)
        note = f"\nEarlier events omitted: {omitted}" if omitted else ""
        return header + note + ("\nRecent trace:\n" + "\n".join(selected) if selected else "")

    def _compact_event(self, event: dict) -> str:
        event = dict(event)
        observation = event.get("observation")
        if observation and len(observation.get("output", "")) > self.max_observation_chars:
            event["observation"] = dict(observation)
            event["observation"]["output"] = observation["output"][-self.max_observation_chars :]
        return json.dumps(event, ensure_ascii=False)
