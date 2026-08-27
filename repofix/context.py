import json
from dataclasses import asdict, dataclass

from .failure_context import FailureContextExtractor, FailureContextResult
from .schemas import PreflightState, TestSnapshot
from .text import compact_text


@dataclass(frozen=True)
class ContextBuildResult:
    text: str
    metadata: dict


class ContextBuilder:
    """Build a bounded prompt from the task and the most recent agent events."""

    def __init__(
        self,
        repo: str,
        task: str,
        max_chars: int = 24_000,
        max_observation_chars: int = 6_000,
        baseline: TestSnapshot | None = None,
        max_baseline_chars: int = 4_000,
        preflight: PreflightState | None = None,
        seed_failure_context: bool = True,
    ):
        self.repo = repo
        self.task = task
        self.max_chars = max_chars
        self.max_observation_chars = max_observation_chars
        self.baseline = baseline
        self.max_baseline_chars = max_baseline_chars
        self.preflight = preflight
        self.seed_failure_context = seed_failure_context
        self.failure_context = FailureContextExtractor(
            repo,
            max_chars=min(6_000, max(max_chars // 4, 0)),
        )

    def build(self, history: list[dict]) -> str:
        return self.build_with_metadata(history).text

    def build_with_metadata(self, history: list[dict]) -> ContextBuildResult:
        progress = self._progress_summary(history)
        preflight = self._preflight_section()
        baseline = self._baseline_section()
        failure_context, failure_result = self._failure_context_section(history)
        fixed = (
            f"Repository: {self.repo}\n"
            "Use the baseline and source snippets as inspection evidence. "
            "Call tools only for missing information, and verify with pytest.\n"
            f"Progress summary: {progress}"
            f"{preflight}"
            f"{baseline}"
            f"{failure_context}"
        )
        task_budget = max(self.max_chars - len(fixed) - len("Task: \n") - 100, 0)
        bounded_task = compact_text(self.task, task_budget)[0]
        header = (
            f"Repository: {self.repo}\n"
            f"Task: {bounded_task}\n"
            "Use the baseline and source snippets as inspection evidence. "
            "Call tools only for missing information, and verify with pytest.\n"
            f"Progress summary: {progress}"
            f"{preflight}"
            f"{baseline}"
            f"{failure_context}"
        )
        budget = max(self.max_chars - len(header) - 100, 0)
        selected: list[str] = []
        used = 0
        oversized_skipped = 0

        for event in reversed(history):
            compact = self._compact_event(event)
            remaining = budget - used
            if len(compact) > remaining:
                if not selected and remaining >= 200:
                    selected.append(compact_text(compact, remaining)[0])
                    break
                oversized_skipped += 1
                continue
            selected.append(compact)
            used += len(compact)

        selected.reverse()
        omitted = len(history) - len(selected)
        note = f"\nEarlier events omitted: {omitted}" if omitted else ""
        context = header + note + ("\nRecent trace:\n" + "\n".join(selected) if selected else "")
        context = compact_text(context, self.max_chars)[0]
        return ContextBuildResult(
            text=context,
            metadata={
                "context_chars": len(context),
                "max_context_chars": self.max_chars,
                "task_chars": len(bounded_task),
                "baseline_included": self.baseline is not None,
                "baseline_section_chars": len(baseline),
                "history_events_total": len(history),
                "history_events_included": len(selected),
                "history_events_omitted": omitted,
                "history_events_skipped_oversized": oversized_skipped,
                "navigation_summary": self._navigation_summary(history),
                "failure_context": {
                    "enabled": self.seed_failure_context,
                    "included": bool(failure_result.text),
                    "chars": len(failure_result.text),
                    "truncated": failure_result.truncated,
                    "sources": [asdict(source) for source in failure_result.sources],
                },
            },
        )

    def _failure_context_section(
        self, history: list[dict]
    ) -> tuple[str, FailureContextResult]:
        if (
            not self.seed_failure_context
            or history
            or self.baseline is None
            or self.baseline.success
        ):
            return "", FailureContextResult("")
        result = self.failure_context.build_result(self.baseline.output)
        if not result.text:
            return "", result
        return f"\nUntrusted traceback-referenced source snippets:\n{result.text}", result

    def _baseline_section(self) -> str:
        if self.baseline is None:
            return ""
        output_budget = min(self.max_baseline_chars, max(self.max_chars // 3, 0))
        output = compact_text(self.baseline.output, output_budget)[0]
        status = "passed" if self.baseline.success else "failed"
        return (
            f"\nIndependent baseline: {status}\n"
            f"Baseline command: {self.baseline.command}\n"
            f"Baseline output:\n{output}"
        )

    def _preflight_section(self) -> str:
        if self.preflight is None:
            return ""
        warnings = [check.message for check in self.preflight.checks if check.status == "warning"]
        suffix = f"; warnings={'; '.join(warnings)}" if warnings else ""
        return f"\nPreflight: {'passed' if self.preflight.success else 'failed'}{suffix}"

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
            post_patch_test = observation.get("metadata", {}).get("post_patch_test")
            if isinstance(post_patch_test, dict):
                latest_pytest = "passed" if post_patch_test.get("success") else "failed"
        files = ", ".join(sorted(changed_files)) if changed_files else "none"
        navigation = ContextBuilder._navigation_summary(history)
        return (
            f"changed_files={files}; latest_agent_pytest={latest_pytest}; "
            f"{navigation}"
        )

    @staticmethod
    def _navigation_summary(history: list[dict]) -> str:
        reads: dict[str, list[tuple[int, int, bool]]] = {}
        searches: list[str] = []
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            metadata = observation.get("metadata", {})
            if action.get("name") == "read" and metadata.get("path"):
                start = metadata.get("start_line")
                end = metadata.get("end_line")
                if isinstance(start, int) and isinstance(end, int):
                    reads.setdefault(metadata["path"], []).append(
                        (start, end, bool(metadata.get("output_truncated")))
                    )
            if action.get("name") == "search" and metadata.get("query") is not None:
                location = metadata.get("path", ".")
                marker = f"{metadata['query']}@{location}({metadata.get('matches', '?')})"
                if marker not in searches:
                    searches.append(marker)

        read_parts = []
        for path, ranges in reads.items():
            rendered = ",".join(
                f"{start}-{end}{'~' if truncated else ''}"
                for start, end, truncated in ranges[-4:]
            )
            read_parts.append(f"{path}:{rendered}")
        read_text = ";".join(read_parts[-6:]) or "none"
        search_text = ",".join(searches[-8:]) or "none"
        summary = f"navigation_reads=[{read_text}]; searches=[{search_text}]"
        return compact_text(summary, 1_200)[0]

    def _compact_event(self, event: dict) -> str:
        event = dict(event)
        observation = event.get("observation")
        if observation and len(observation.get("output", "")) > self.max_observation_chars:
            event["observation"] = dict(observation)
            event["observation"]["output"] = compact_text(
                observation["output"], self.max_observation_chars
            )[0]
        return json.dumps(event, ensure_ascii=False)
