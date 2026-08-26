import json
import re
from typing import Protocol

from .config import Settings
from .schemas import Action


class ModelProvider(Protocol):
    def next_action(self, context: str) -> Action: ...


class OpenAICompatibleProvider:
    """真实模型入口；兼容 OpenAI 风格 chat completions API。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        from openai import OpenAI

        settings = Settings.from_env()
        resolved_key = api_key or settings.api_key
        if not resolved_key:
            raise ValueError("Missing REPOFIX_API_KEY. Set it in the environment before running RepoFix.")
        self.model = model or settings.model
        self.client = OpenAI(
            base_url=base_url or settings.base_url,
            api_key=resolved_key,
        )

    def next_action(self, context: str) -> Action:
        prompt = "Choose exactly one JSON action. Allowed names: list, search, read, apply_patch, run_command, git_diff, git_status, finish. Schema: {name:string, arguments:object, rationale:string}. For finish arguments use {summary:string}.\n\n" + context
        response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0)
        data = parse_action_json(response.choices[0].message.content or "")
        return Action(**data)


def parse_action_json(text: str) -> dict:
    """Accept plain JSON or a JSON markdown fence from compatible models."""
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    payload = match.group(1) if match else text.strip()
    data = json.loads(payload)
    allowed = {"list", "search", "read", "apply_patch", "run_command", "git_diff", "git_status", "finish"}
    if data.get("name") not in allowed or not isinstance(data.get("arguments", {}), dict):
        raise ValueError("Model returned an invalid action")
    data.setdefault("arguments", {})
    data.setdefault("rationale", "")
    return data
