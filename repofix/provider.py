import json
import os
from typing import Protocol
from .schemas import Action

class ModelProvider(Protocol):
    def next_action(self, context: str) -> Action: ...

class OpenAICompatibleProvider:
    """真实模型入口；兼容 OpenAI 风格 chat completions API。"""
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        from openai import OpenAI
        self.model = model or os.getenv("REPOFIX_MODEL", "gpt-4o-mini")
        self.client = OpenAI(
            base_url=base_url or os.getenv("REPOFIX_BASE_URL") or None,
            api_key=api_key or os.getenv("REPOFIX_API_KEY"),
        )

    def next_action(self, context: str) -> Action:
        prompt = "Choose exactly one JSON action. Allowed names: list, search, read, apply_patch, run_command, git_diff, git_status, finish. Schema: {name:string, arguments:object, rationale:string}. For finish arguments use {summary:string}.\n\n" + context
        response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0)
        data = json.loads(response.choices[0].message.content)
        return Action(**data)
