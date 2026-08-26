import json
import re
import time
from typing import Protocol

from .config import Settings
from .registry import render_action_instructions, validate_action
from .schemas import Action, ModelDecision, TokenUsage


class ModelProvider(Protocol):
    def next_action(self, context: str) -> ModelDecision: ...


class OpenAICompatibleProvider:
    """真实模型入口；兼容 OpenAI 风格 chat completions API。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_transient_retries: int = 3,
        max_format_retries: int = 2,
    ):
        from openai import OpenAI

        settings = Settings.from_env()
        resolved_key = api_key or settings.api_key
        if not resolved_key:
            raise ValueError("Missing REPOFIX_API_KEY. Set it in the environment before running RepoFix.")
        self.model = model or settings.model
        self.max_transient_retries = max_transient_retries
        self.max_format_retries = max_format_retries
        self.client = OpenAI(
            base_url=base_url or settings.base_url,
            api_key=resolved_key,
            max_retries=0,
            timeout=settings.request_timeout_seconds,
        )

    def next_action(self, context: str) -> ModelDecision:
        prompt = f"""Choose exactly one JSON action and return no other text.
Action envelope: {{"name": string, "arguments": object, "rationale": string}}
Allowed tools and exact arguments:
{render_action_instructions()}
Do not send a unified diff to apply_patch; it requires the complete file content.

""" + context
        total_usage = TokenUsage()
        last_text = ""
        for attempt in range(self.max_format_retries + 1):
            response = self._create_completion(prompt)
            total_usage.add(extract_usage(response))
            last_text = response.choices[0].message.content or ""
            try:
                data = parse_action_json(last_text)
                return ModelDecision(
                    action=Action(**data),
                    usage=total_usage,
                    model=self.model,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                if attempt == self.max_format_retries:
                    raise ValueError(f"invalid model action after retries: {exc}; output={last_text[:500]!r}") from exc
                prompt += (
                    "\nYour previous response was invalid JSON or violated the action schema. "
                    f"Error: {exc}. Return one corrected JSON action only.\n"
                    f"Previous response: {last_text[:1000]}\n"
                )
        raise RuntimeError("unreachable")

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
    data.setdefault("arguments", {})
    data.setdefault("rationale", "")
    error = validate_action(data.get("name", ""), data["arguments"])
    if error:
        raise ValueError(f"Model returned an invalid action: {error}")
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
