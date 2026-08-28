import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str | None
    api_key: str | None
    model: str
    max_steps: int
    max_context_chars: int
    request_timeout_seconds: float
    max_requests: int
    max_tokens: int
    input_cost_per_million: float
    output_cost_per_million: float
    cached_input_cost_per_million: float
    max_identical_actions: int
    max_changed_files: int
    rollback_on_failure: bool
    test_command: str
    final_test_command: str | None
    execution_backend: str
    docker_image: str
    command_timeout_seconds: int
    max_output_tokens: int
    patch_max_output_tokens: int
    json_mode: bool
    native_tool_calls: bool
    seed_failure_context: bool
    verify_after_patch: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.getenv("REPOFIX_BASE_URL") or None,
            api_key=os.getenv("REPOFIX_API_KEY") or None,
            model=os.getenv("REPOFIX_MODEL", "gpt-4o-mini"),
            max_steps=int(os.getenv("REPOFIX_MAX_STEPS", "12")),
            max_context_chars=int(os.getenv("REPOFIX_MAX_CONTEXT_CHARS", "24000")),
            request_timeout_seconds=float(os.getenv("REPOFIX_REQUEST_TIMEOUT_SECONDS", "45")),
            max_requests=int(os.getenv("REPOFIX_MAX_REQUESTS", "0")),
            max_tokens=int(os.getenv("REPOFIX_MAX_TOKENS", "0")),
            input_cost_per_million=float(os.getenv("REPOFIX_INPUT_COST_PER_MILLION", "0")),
            output_cost_per_million=float(os.getenv("REPOFIX_OUTPUT_COST_PER_MILLION", "0")),
            cached_input_cost_per_million=float(os.getenv("REPOFIX_CACHED_INPUT_COST_PER_MILLION", "0")),
            max_identical_actions=int(os.getenv("REPOFIX_MAX_IDENTICAL_ACTIONS", "2")),
            max_changed_files=int(os.getenv("REPOFIX_MAX_CHANGED_FILES", "5")),
            rollback_on_failure=os.getenv("REPOFIX_ROLLBACK_ON_FAILURE", "0").lower()
            in {"1", "true", "yes"},
            test_command=os.getenv("REPOFIX_TEST_COMMAND", "pytest -q"),
            final_test_command=os.getenv("REPOFIX_FINAL_TEST_COMMAND") or None,
            execution_backend=os.getenv("REPOFIX_EXECUTION_BACKEND", "local"),
            docker_image=os.getenv("REPOFIX_DOCKER_IMAGE", "repofix-pytest:latest"),
            command_timeout_seconds=int(os.getenv("REPOFIX_COMMAND_TIMEOUT_SECONDS", "30")),
            max_output_tokens=int(os.getenv("REPOFIX_MAX_OUTPUT_TOKENS", "2048")),
            patch_max_output_tokens=int(
                os.getenv("REPOFIX_PATCH_MAX_OUTPUT_TOKENS", "4096")
            ),
            json_mode=os.getenv("REPOFIX_JSON_MODE", "1").lower()
            in {"1", "true", "yes"},
            native_tool_calls=os.getenv("REPOFIX_NATIVE_TOOL_CALLS", "1").lower()
            in {"1", "true", "yes"},
            seed_failure_context=os.getenv("REPOFIX_SEED_FAILURE_CONTEXT", "1").lower()
            in {"1", "true", "yes"},
            verify_after_patch=os.getenv("REPOFIX_VERIFY_AFTER_PATCH", "0").lower()
            in {"1", "true", "yes"},
        )
