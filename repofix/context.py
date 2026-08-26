import json

from .text import compact_text


class ContextBuilder:
    """Build a bounded prompt from the task and the most recent agent events."""

    def __init__(self, repo: str, task: str, max_chars: int = 24_000, max_observation_chars: int = 6_000):
        self.repo = repo
        self.task = task
        self.max_chars = max_chars
        self.max_observation_chars = max_observation_chars

    def build(self, history: list[dict]) -> str:
        progress = self._progress_summary(history)
        fixed = (
            f"Repository: {self.repo}\n"
            "Continue from the recent trace below. Inspect before editing and verify with pytest.\n"
            f"Progress summary: {progress}"
        )
        task_budget = max(self.max_chars - len(fixed) - len("Task: \n") - 100, 0)
        bounded_task = compact_text(self.task, task_budget)[0]
        header = (
            f"Repository: {self.repo}\n"
            f"Task: {bounded_task}\n"
            "Continue from the recent trace below. Inspect before editing and verify with pytest.\n"
            f"Progress summary: {progress}"
        )
        budget = max(self.max_chars - len(header) - 100, 0)
        selected: list[str] = []
        used = 0

        for event in reversed(history):
            compact = self._compact_event(event)
            remaining = budget - used
            if len(compact) > remaining:
                if not selected and remaining >= 200:
                    selected.append(compact_text(compact, remaining)[0])
                break
            selected.append(compact)
            used += len(compact)

        selected.reverse()
        omitted = len(history) - len(selected)
        note = f"\nEarlier events omitted: {omitted}" if omitted else ""
        context = header + note + ("\nRecent trace:\n" + "\n".join(selected) if selected else "")
        return compact_text(context, self.max_chars)[0]

    @staticmethod
    def _progress_summary(history: list[dict]) -> str:
        changed_files = set()
        latest_pytest = "not run by agent"
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            if action.get("name") == "apply_patch" and observation.get("metadata", {}).get("changed"):
                changed_files.add(observation["metadata"]["path"])
            if action.get("name") == "run_command":
                latest_pytest = "passed" if observation.get("success") else "failed"
        files = ", ".join(sorted(changed_files)) if changed_files else "none"
        return f"changed_files={files}; latest_agent_pytest={latest_pytest}"

    def _compact_event(self, event: dict) -> str:
        event = dict(event)
        observation = event.get("observation")
        if observation and len(observation.get("output", "")) > self.max_observation_chars:
            event["observation"] = dict(observation)
            event["observation"]["output"] = compact_text(
                observation["output"], self.max_observation_chars
            )[0]
        return json.dumps(event, ensure_ascii=False)
