import json
import re
import time
from typing import Protocol

from .config import Settings
from .schemas import Action, ModelDecision, TokenUsage


class ModelProvider(Protocol):
    def next_action(self, context: str) -> ModelDecision: ...


class OpenAICompatibleProvider:
    """真实模型入口；兼容 OpenAI 风格 chat completions API。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None, max_transient_retries: int = 3):
        from openai import OpenAI

        settings = Settings.from_env()
        resolved_key = api_key or settings.api_key
        if not resolved_key:
            raise ValueError("Missing REPOFIX_API_KEY. Set it in the environment before running RepoFix.")
        self.model = model or settings.model
        self.max_transient_retries = max_transient_retries
        self.client = OpenAI(
            base_url=base_url or settings.base_url,
            api_key=resolved_key,
            max_retries=0,
            timeout=settings.request_timeout_seconds,
        )

    def next_action(self, context: str) -> ModelDecision:
        prompt = """Choose exactly one JSON action and return no other text.
Action envelope: {"name": string, "arguments": object, "rationale": string}
Allowed tools and exact arguments:
- list: {}
- search: {"query": "text"}
- read: {"path": "relative/path.py"}
- apply_patch: {"path": "relative/path.py", "content": "complete replacement file content"}
- run_command: {"command": "pytest -q"}
- git_diff: {}
- git_status: {}
- finish: {"summary": "what was fixed and how it was verified"}
Do not send a unified diff to apply_patch; it requires the complete file content.

""" + context
        response = self._create_completion(prompt)
        data = parse_action_json(response.choices[0].message.content or "")
        return ModelDecision(
            action=Action(**data),
            usage=extract_usage(response),
            model=self.model,
        )

    def _create_completion(self, prompt: str):
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

        transient_errors = (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError)
        for attempt in range(self.max_transient_retries + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
            except transient_errors as exc:
                if attempt == self.max_transient_retries:
                    raise
                delay = retry_delay_seconds(str(exc)) if isinstance(exc, RateLimitError) else transient_retry_delay(attempt)
                time.sleep(delay)
        raise RuntimeError("unreachable")


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


def retry_delay_seconds(error_text: str) -> float:
    match = re.search(r"retry in ([0-9.]+)s", error_text, re.IGNORECASE)
    return min(max(float(match.group(1)) + 1, 1), 60) if match else 30


def transient_retry_delay(attempt: int) -> float:
    return min(2 * (2**attempt), 15)


def extract_usage(response) -> TokenUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage(requests=1)
    details = getattr(usage, "prompt_tokens_details", None)
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
        cached_input_tokens=getattr(details, "cached_tokens", 0) or 0,
        requests=1,
    )
