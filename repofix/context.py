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
        repair_phase = self._repair_phase(history)
        working_history, working_set_pruned = self._revision_working_set(
            history, repair_phase
        )
        progress = self._progress_summary(history, working_history)
        revision_navigation_cap = self._revision_navigation_cap(history)
        next_priority = self._next_priority(repair_phase)
        preflight = self._preflight_section()
        baseline_superseded = self.baseline is not None and self._has_new_test_evidence(
            history
        )
        baseline = self._baseline_section(history)
        failure_context, failure_result = self._failure_context_section(history)
        fixed = (
            f"Repository: {self.repo}\n"
            "Use the baseline and source snippets as inspection evidence. "
            "Call tools only for missing information, and verify with pytest.\n"
            f"Progress summary: {progress}"
            f"\nNext priority: {next_priority}"
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
            f"\nNext priority: {next_priority}"
            f"{preflight}"
            f"{baseline}"
            f"{failure_context}"
        )
        budget = max(self.max_chars - len(header) - 100, 0)
        selected: list[str] = []
        used = 0
        oversized_skipped = 0

        context_history, deduplicated = self._deduplicate_navigation(working_history)
        for event in reversed(context_history):
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
                "baseline_output_superseded": baseline_superseded,
                "history_events_total": len(history),
                "history_events_included": len(selected),
                "history_events_omitted": omitted,
                "history_events_deduplicated": deduplicated,
                "revision_working_set_active": working_set_pruned > 0,
                "revision_working_set_pruned": working_set_pruned,
                "history_events_skipped_oversized": oversized_skipped,
                "navigation_summary": self._navigation_summary(working_history),
                "repair_phase": repair_phase,
                "revision_navigation_cap": revision_navigation_cap,
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

    def _baseline_section(self, history: list[dict]) -> str:
        if self.baseline is None:
            return ""
        status = "passed" if self.baseline.success else "failed"
        if self._has_new_test_evidence(history):
            return (
                f"\nIndependent baseline: {status} (output superseded by newer pytest evidence)\n"
                f"Baseline command: {self.baseline.command}"
            )
        output_budget = min(self.max_baseline_chars, max(self.max_chars // 3, 0))
        output = compact_text(self.baseline.output, output_budget)[0]
        return (
            f"\nIndependent baseline: {status}\n"
            f"Baseline command: {self.baseline.command}\n"
            f"Baseline output:\n{output}"
        )

    @staticmethod
    def _has_new_test_evidence(history: list[dict]) -> bool:
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            if ContextBuilder._is_pytest_evidence(action, observation):
                return True
            if isinstance(observation.get("metadata", {}).get("post_patch_test"), dict):
                return True
        return False

    @staticmethod
    def _is_pytest_evidence(action: dict, observation: dict) -> bool:
        if action.get("name") != "run_command":
            return False
        metadata = observation.get("metadata", {})
        if "return_code" in metadata or metadata.get("timed_out") is True:
            return True
        # Checkpoints created before execution metadata was recorded used an
        # empty metadata object for completed pytest actions.
        return not metadata

    @staticmethod
    def _deduplicate_navigation(history: list[dict]) -> tuple[list[dict], int]:
        """Keep the latest copy of repeated read/search evidence in model context."""
        seen: set[tuple] = set()
        selected: list[dict] = []
        deduplicated = 0
        for event in reversed(history):
            action = event.get("action", {})
            observation = event.get("observation", {})
            metadata = observation.get("metadata", {})
            name = action.get("name")
            signature: tuple | None = None
            if name == "read" and metadata.get("path"):
                signature = (
                    name,
                    metadata["path"],
                    metadata.get("start_line"),
                    metadata.get("end_line"),
                )
            elif name == "search" and metadata.get("query") is not None:
                signature = (name, metadata.get("path", "."), metadata["query"])
            if signature is not None:
                if signature in seen:
                    deduplicated += 1
                    continue
                seen.add(signature)
            selected.append(event)
        selected.reverse()
        return selected, deduplicated

    @staticmethod
    def _revision_working_set(
        history: list[dict], repair_phase: str
    ) -> tuple[list[dict], int]:
        if repair_phase not in {"patch_needs_revision", "patch_due"}:
            return history, 0
        changed_patch_indices: list[int] = []
        latest_failed_test: int | None = None
        for index, event in enumerate(history):
            action = event.get("action", {})
            observation = event.get("observation", {})
            if action.get("name") == "apply_patch" and observation.get(
                "metadata", {}
            ).get("changed"):
                changed_patch_indices.append(index)
                latest_failed_test = None
            if ContextBuilder._is_pytest_evidence(action, observation) and not observation.get(
                "success", False
            ):
                latest_failed_test = index
            post_patch_test = observation.get("metadata", {}).get("post_patch_test")
            if isinstance(post_patch_test, dict) and not post_patch_test.get(
                "success", False
            ):
                latest_failed_test = index
        if latest_failed_test is None:
            return history, 0
        patch_candidates = [
            index for index in changed_patch_indices if index <= latest_failed_test
        ]
        if not patch_candidates:
            return history, 0
        patch_index = patch_candidates[-1]
        selected_indices = {patch_index, latest_failed_test}
        selected_indices.update(range(latest_failed_test + 1, len(history)))
        selected = [
            event for index, event in enumerate(history) if index in selected_indices
        ]
        return selected, len(history) - len(selected)

    def _preflight_section(self) -> str:
        if self.preflight is None:
            return ""
        warnings = [check.message for check in self.preflight.checks if check.status == "warning"]
        suffix = f"; warnings={'; '.join(warnings)}" if warnings else ""
        return f"\nPreflight: {'passed' if self.preflight.success else 'failed'}{suffix}"

    @staticmethod
    def _progress_summary(
        history: list[dict], navigation_history: list[dict] | None = None
    ) -> str:
        changed_files = set()
        latest_pytest = "not run by agent"
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            if action.get("name") == "apply_patch" and observation.get("metadata", {}).get("changed"):
                changed_files.add(observation["metadata"]["path"])
                latest_pytest = "not run for current patch"
            if ContextBuilder._is_pytest_evidence(action, observation):
                latest_pytest = "passed" if observation.get("success") else "failed"
            post_patch_test = observation.get("metadata", {}).get("post_patch_test")
            if isinstance(post_patch_test, dict):
                latest_pytest = "passed" if post_patch_test.get("success") else "failed"
        files = ", ".join(sorted(changed_files)) if changed_files else "none"
        navigation = ContextBuilder._navigation_summary(
            history if navigation_history is None else navigation_history
        )
        return (
            f"changed_files={files}; latest_agent_pytest={latest_pytest}; "
            f"repair_phase={ContextBuilder._repair_phase(history)}; {navigation}"
        )

    @staticmethod
    def _repair_phase(history: list[dict]) -> str:
        changed = False
        changed_files: set[str] = set()
        latest_pytest: bool | None = None
        latest_pytest_output = ""
        successful_reads = 0
        successful_searches = 0
        empty_searches = 0
        failed_patches = 0
        navigation_since_patch = 0
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            name = action.get("name")
            success = bool(observation.get("success", True))
            if name == "read" and success:
                successful_reads += 1
                navigation_since_patch += 1
            elif name == "search" and success:
                if observation.get("metadata", {}).get("matches", 0) > 0:
                    successful_searches += 1
                    navigation_since_patch += 1
                else:
                    empty_searches += 1
            elif name == "apply_patch":
                navigation_since_patch = 0
                if success and observation.get("metadata", {}).get("changed"):
                    changed = True
                    latest_pytest = None
                    latest_pytest_output = ""
                    path = observation.get("metadata", {}).get("path")
                    if path:
                        changed_files.add(str(path).replace("\\", "/"))
                elif not success:
                    failed_patches += 1
            elif ContextBuilder._is_pytest_evidence(action, observation):
                latest_pytest = success
                latest_pytest_output = "" if success else observation.get("output", "")
            post_patch_test = observation.get("metadata", {}).get("post_patch_test")
            if isinstance(post_patch_test, dict):
                latest_pytest = bool(post_patch_test.get("success"))
                latest_pytest_output = (
                    "" if latest_pytest else str(post_patch_test.get("output", ""))
                )

        if changed and latest_pytest is True:
            return "verified_patch"
        if changed and latest_pytest is False:
            navigation_cap = ContextBuilder._revision_cap_for_failure(
                changed_files, latest_pytest_output
            )
            if navigation_since_patch >= navigation_cap:
                return "patch_due"
            return "patch_needs_revision"
        if changed:
            return "patch_needs_verification"
        if failed_patches:
            if navigation_since_patch >= 2:
                return "patch_due"
            return "patch_attempt_failed"
        if empty_searches >= 3 and not successful_reads and not successful_searches:
            return "search_exhausted"
        if successful_reads + successful_searches >= 5:
            return "patch_due"
        if successful_reads >= 2 or (successful_reads and successful_searches):
            return "ready_to_patch"
        if successful_reads or successful_searches:
            return "inspecting"
        return "locating"

    @staticmethod
    def _revision_cap_for_failure(
        changed_files: set[str], pytest_output: str
    ) -> int:
        normalized = pytest_output.replace("\\", "/")
        if any(f"{path}:" in normalized for path in changed_files):
            return 1
        return 2

    @staticmethod
    def _revision_navigation_cap(history: list[dict]) -> int | None:
        changed_files: set[str] = set()
        latest_pytest: bool | None = None
        latest_pytest_output = ""
        for event in history:
            action = event.get("action", {})
            observation = event.get("observation", {})
            if action.get("name") == "apply_patch" and observation.get(
                "metadata", {}
            ).get("changed"):
                latest_pytest = None
                latest_pytest_output = ""
                path = observation.get("metadata", {}).get("path")
                if path:
                    changed_files.add(str(path).replace("\\", "/"))
            elif ContextBuilder._is_pytest_evidence(action, observation):
                latest_pytest = bool(observation.get("success"))
                latest_pytest_output = (
                    "" if latest_pytest else str(observation.get("output", ""))
                )
            post_patch_test = observation.get("metadata", {}).get("post_patch_test")
            if isinstance(post_patch_test, dict):
                latest_pytest = bool(post_patch_test.get("success"))
                latest_pytest_output = (
                    "" if latest_pytest else str(post_patch_test.get("output", ""))
                )
        if not changed_files or latest_pytest is not False:
            return None
        return ContextBuilder._revision_cap_for_failure(
            changed_files, latest_pytest_output
        )

    @staticmethod
    def _next_priority(repair_phase: str) -> str:
        priorities = {
            "locating": "Locate the smallest relevant source area.",
            "search_exhausted": "Stop guessing symbol names. List files or read a known likely source path.",
            "inspecting": "Read only the missing narrow source range needed for a repair.",
            "ready_to_patch": "If the evidence supports the cause, apply the smallest localized patch now instead of rereading known code.",
            "patch_due": "Do not call list, search, or read again. Apply the smallest localized patch now using exact text already observed.",
            "patch_attempt_failed": "Use the patch failure observation to correct the localized edit without broadening scope.",
            "patch_needs_verification": "Run the focused pytest command for the changed behavior.",
            "patch_needs_revision": "Use the latest pytest failure to revise the existing localized patch.",
            "verified_patch": "Inspect the diff if needed, then finish with the verification summary.",
        }
        return priorities[repair_phase]

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
