from repofix.context import ContextBuilder
from repofix.schemas import PreflightCheck, PreflightState, TestSnapshot as Snapshot


def test_context_is_bounded_and_keeps_latest_event():
    history = [
        {"step": i, "observation": {"output": f"event-{i}-" + "x" * 500}}
        for i in range(20)
    ]
    context = ContextBuilder("repo", "task", max_chars=1500, max_observation_chars=600).build(history)
    assert len(context) <= 1500
    assert "event-19" in context
    assert "Earlier events omitted" in context


def test_context_preserves_progress_summary_and_output_head_tail():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {"output": "updated", "metadata": {"changed": True, "path": "a.py"}},
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {"output": "TRACEBACK-START" + "x" * 500 + "SUMMARY-END", "success": False},
        },
    ]
    context = ContextBuilder("repo", "task", max_chars=700, max_observation_chars=120).build(history)
    assert "changed_files=a.py" in context
    assert "latest_agent_pytest=failed" in context
    assert "repair_phase=patch_needs_revision" in context
    assert "TRACEBACK-START" in context
    assert "SUMMARY-END" in context
    assert "chars omitted" in context


def test_context_remains_bounded_with_oversized_task():
    context = ContextBuilder("repo", "very long task " * 1_000, max_chars=500).build([])
    assert len(context) <= 500
    assert "chars omitted" in context
    assert "Progress summary" in context


def test_context_includes_bounded_independent_baseline():
    baseline = Snapshot(
        False,
        "TRACEBACK-START\n" + "x" * 1_000 + "\n1 failed SUMMARY-END",
        command="pytest -q tests/unit",
    )
    context = ContextBuilder(
        "repo",
        "fix tests",
        max_chars=1_200,
        baseline=baseline,
        max_baseline_chars=300,
    ).build([])

    assert len(context) <= 1_200
    assert "Independent baseline: failed" in context
    assert "Baseline command: pytest -q tests/unit" in context
    assert "TRACEBACK-START" in context
    assert "SUMMARY-END" in context
    assert "chars omitted" in context


def test_context_collapses_baseline_output_after_new_pytest_evidence():
    baseline = Snapshot(
        False,
        "OLD-TRACEBACK\n" + "x" * 1_000 + "\nOLD-SUMMARY",
        command="pytest -q tests/unit",
    )
    history = [
        {
            "step": 1,
            "action": {"name": "run_command"},
            "observation": {"success": False, "output": "NEW-TRACEBACK"},
        }
    ]

    result = ContextBuilder(
        "repo", "fix tests", baseline=baseline, max_baseline_chars=2_000
    ).build_with_metadata(history)

    assert "output superseded by newer pytest evidence" in result.text
    assert "Baseline command: pytest -q tests/unit" in result.text
    assert "OLD-TRACEBACK" not in result.text
    assert "NEW-TRACEBACK" in result.text
    assert result.metadata["baseline_section_chars"] < 200
    assert result.metadata["baseline_output_superseded"] is True


def test_context_collapses_baseline_after_automatic_post_patch_test():
    baseline = Snapshot(False, "OLD-FAILURE", command="pytest -q tests/unit")
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "output": "PATCHED\nNEW-FAILURE",
                "metadata": {
                    "changed": True,
                    "path": "src/parser.py",
                    "post_patch_test": {"success": False},
                },
            },
        }
    ]

    context = ContextBuilder("repo", "fix tests", baseline=baseline).build(history)

    assert "output superseded by newer pytest evidence" in context
    assert "OLD-FAILURE" not in context
    assert "NEW-FAILURE" in context


def test_context_includes_preflight_warnings():
    preflight = PreflightState(
        True,
        [PreflightCheck("project_metadata", "warning", "no standard project metadata found")],
    )

    context = ContextBuilder("repo", "task", preflight=preflight).build([])

    assert "Preflight: passed" in context
    assert "no standard project metadata found" in context


def test_context_seeds_traceback_source_only_on_first_model_request(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    baseline = Snapshot(False, "calculator.py:2: AssertionError")
    builder = ContextBuilder(str(tmp_path), "fix add", baseline=baseline)

    first = builder.build([])
    later = builder.build([{"step": 1, "action": {"name": "list"}}])

    assert "Untrusted traceback-referenced source snippets" in first
    assert "return a - b" in first
    assert "Call tools only for missing information" in first
    assert "traceback-referenced source snippets" not in later

    details = builder.build_with_metadata([])
    metadata = details.metadata
    assert metadata["context_chars"] == len(details.text)
    assert metadata["max_context_chars"] == 24_000
    assert metadata["failure_context"]["included"] is True
    assert metadata["failure_context"]["sources"][0]["path"] == "calculator.py"
    assert metadata["failure_context"]["sources"][0]["reason"] == "traceback"
    assert metadata["history_events_total"] == 0
    assert metadata["repair_phase"] == "locating"


def test_context_can_disable_failure_source_seeding(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    baseline = Snapshot(False, "calculator.py:2: AssertionError")

    result = ContextBuilder(
        str(tmp_path),
        "fix add",
        baseline=baseline,
        seed_failure_context=False,
    ).build_with_metadata([])

    assert "traceback-referenced source snippets" not in result.text
    assert result.metadata["failure_context"]["enabled"] is False
    assert result.metadata["failure_context"]["included"] is False
    assert result.metadata["failure_context"]["sources"] == []


def test_context_keeps_compact_navigation_memory():
    history = [
        {
            "step": 1,
            "action": {"name": "search", "arguments": {"query": "parse_key"}},
            "observation": {
                "output": "src/parser.py:463:def parse_key",
                "metadata": {"query": "parse_key", "path": ".", "matches": 1},
            },
        },
        {
            "step": 2,
            "action": {"name": "read", "arguments": {"path": "src/parser.py"}},
            "observation": {
                "output": "source",
                "metadata": {
                    "path": "src/parser.py",
                    "start_line": 440,
                    "end_line": 485,
                    "total_lines": 700,
                },
            },
        },
    ]

    context = ContextBuilder("repo", "task").build(history)

    assert "navigation_reads=[src/parser.py:440-485]" in context
    assert "searches=[parse_key@.(1)]" in context

    metadata = ContextBuilder("repo", "task").build_with_metadata(history).metadata
    assert metadata["navigation_summary"] == (
        "navigation_reads=[src/parser.py:440-485]; searches=[parse_key@.(1)]"
    )
    assert metadata["repair_phase"] == "ready_to_patch"
    assert "apply the smallest localized patch now" in context


def test_context_guides_verified_patch_toward_finish():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {
                    "changed": True,
                    "path": "src/parser.py",
                    "post_patch_test": {"success": True},
                },
            },
        }
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "verified_patch"
    assert "then finish with the verification summary" in result.text


def test_context_marks_patch_due_after_excessive_successful_navigation():
    history = []
    for step in range(1, 6):
        history.append(
            {
                "step": step,
                "action": {"name": "read", "arguments": {"path": "src/parser.py"}},
                "observation": {
                    "success": True,
                    "output": f"source-{step}",
                    "metadata": {
                        "path": "src/parser.py",
                        "start_line": step * 10,
                        "end_line": step * 10 + 5,
                    },
                },
            }
        )

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"
    assert "Do not call list, search, or read again" in result.text


def test_context_forces_revision_after_two_reads_following_failed_verification():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {
                    "changed": True,
                    "path": "src/parser.py",
                    "post_patch_test": {"success": False},
                },
            },
        },
        {"step": 2, "action": {"name": "read"}, "observation": {"success": True}},
        {
            "step": 3,
            "action": {"name": "search"},
            "observation": {"success": True, "metadata": {"matches": 1}},
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"
    assert "Do not call list, search, or read again" in result.text


def test_context_forces_revision_after_one_read_when_traceback_points_to_patch():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "src/parser.py:42: ValueError: got partial footer",
            },
        },
        {
            "step": 3,
            "action": {"name": "read"},
            "observation": {"success": True},
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"
    assert result.metadata["revision_navigation_cap"] == 1


def test_context_keeps_two_reads_when_failure_only_points_to_test():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "tests/test_parser.py:12: AssertionError",
            },
        },
        {
            "step": 3,
            "action": {"name": "read"},
            "observation": {"success": True},
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_revision"
    assert result.metadata["revision_navigation_cap"] == 2


def test_context_forces_retry_after_two_reads_following_rejected_patch():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {"success": False, "output": "old_text was not unique"},
        },
        {"step": 2, "action": {"name": "read"}, "observation": {"success": True}},
        {"step": 3, "action": {"name": "read"}, "observation": {"success": True}},
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"


def test_empty_searches_do_not_create_patch_readiness_and_eventually_force_read():
    history = [
        {
            "step": step,
            "action": {"name": "search", "arguments": {"query": f"guess_{step}"}},
            "observation": {"success": True, "metadata": {"matches": 0}},
        }
        for step in range(1, 4)
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "search_exhausted"
    assert "Stop guessing symbol names" in result.text


def test_context_skips_oversized_middle_event_and_keeps_smaller_evidence():
    history = [
        {"step": 1, "action": {"name": "search"}, "observation": {"output": "EARLY-LANDMARK"}},
        {"step": 2, "action": {"name": "read"}, "observation": {"output": "x" * 5_000}},
        {"step": 3, "action": {"name": "search"}, "observation": {"output": "LATEST-LANDMARK"}},
    ]

    builder = ContextBuilder(
        "repo", "task", max_chars=1_000, max_observation_chars=4_000
    )
    result = builder.build_with_metadata(history)
    context = result.text

    assert "LATEST-LANDMARK" in context
    assert "EARLY-LANDMARK" in context
    assert len(context) <= 1_000
    assert result.metadata["history_events_skipped_oversized"] == 1


def test_context_keeps_only_latest_repeated_navigation_evidence():
    history = [
        {
            "step": 1,
            "action": {"name": "read"},
            "observation": {
                "output": "OLD-SOURCE",
                "metadata": {"path": "src/parser.py", "start_line": 10, "end_line": 20},
            },
        },
        {
            "step": 2,
            "action": {"name": "search"},
            "observation": {
                "output": "OLD-SEARCH",
                "metadata": {"path": ".", "query": "parse", "matches": 1},
            },
        },
        {
            "step": 3,
            "action": {"name": "read"},
            "observation": {
                "output": "CURRENT-SOURCE",
                "metadata": {"path": "src/parser.py", "start_line": 10, "end_line": 20},
            },
        },
        {
            "step": 4,
            "action": {"name": "search"},
            "observation": {
                "output": "CURRENT-SEARCH",
                "metadata": {"path": ".", "query": "parse", "matches": 1},
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert "CURRENT-SOURCE" in result.text
    assert "CURRENT-SEARCH" in result.text
    assert "OLD-SOURCE" not in result.text
    assert "OLD-SEARCH" not in result.text
    assert result.metadata["history_events_total"] == 4
    assert result.metadata["history_events_included"] == 2
    assert result.metadata["history_events_omitted"] == 2
    assert result.metadata["history_events_deduplicated"] == 2


def test_revision_working_set_drops_pre_patch_navigation_only_from_prompt():
    history = [
        {
            "step": 1,
            "action": {"name": "search"},
            "observation": {
                "success": True,
                "output": "EARLY-SEARCH",
                "metadata": {"query": "parser", "path": ".", "matches": 1},
            },
        },
        {
            "step": 2,
            "action": {"name": "read"},
            "observation": {
                "success": True,
                "output": "EARLY-SOURCE",
                "metadata": {
                    "path": "src/parser.py",
                    "start_line": 1,
                    "end_line": 20,
                },
            },
        },
        {
            "step": 3,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "output": "PATCH-RESULT",
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 4,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "LATEST-FAILURE src/parser.py:12",
            },
        },
        {
            "step": 5,
            "action": {"name": "read"},
            "observation": {
                "success": True,
                "output": "CURRENT-SOURCE",
                "metadata": {
                    "path": "src/parser.py",
                    "start_line": 8,
                    "end_line": 16,
                },
            },
        },
    ]
    original = [dict(event) for event in history]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"
    assert result.metadata["revision_working_set_active"] is True
    assert result.metadata["revision_working_set_pruned"] == 2
    assert result.metadata["history_events_total"] == 5
    assert result.metadata["history_events_included"] == 3
    assert "PATCH-RESULT" in result.text
    assert "LATEST-FAILURE" in result.text
    assert "CURRENT-SOURCE" in result.text
    assert "EARLY-SEARCH" not in result.text
    assert "EARLY-SOURCE" not in result.text
    assert history == original


def test_patch_due_before_first_change_keeps_navigation_history():
    history = [
        {
            "step": step,
            "action": {"name": "read"},
            "observation": {
                "success": True,
                "output": f"SOURCE-{step}",
                "metadata": {
                    "path": "src/parser.py",
                    "start_line": step,
                    "end_line": step,
                },
            },
        }
        for step in range(1, 6)
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_due"
    assert result.metadata["revision_working_set_active"] is False
    assert result.metadata["revision_working_set_pruned"] == 0
    assert "SOURCE-1" in result.text
    assert "SOURCE-5" in result.text


def test_new_revision_patch_invalidates_older_failed_pytest_evidence():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "src/parser.py:42: AssertionError",
            },
        },
        {"step": 3, "action": {"name": "read"}, "observation": {"success": True}},
        {
            "step": 4,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_verification"
    assert result.metadata["revision_navigation_cap"] is None
    assert result.metadata["revision_working_set_active"] is False
    assert result.metadata["phase_working_set_active"] is True
    assert result.metadata["phase_working_set_kind"] == "verification"
    assert "latest_agent_pytest=not run for current patch" in result.text


def test_new_revision_patch_uses_its_own_failed_automatic_test():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {"success": False, "output": "OLD-FAILURE"},
        },
        {
            "step": 3,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {
                    "changed": True,
                    "path": "src/parser.py",
                    "post_patch_test": {
                        "success": False,
                        "output": "src/parser.py:50: CURRENT-FAILURE",
                    },
                },
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_revision"
    assert result.metadata["revision_navigation_cap"] == 1
    assert result.metadata["revision_working_set_active"] is True
    assert "CURRENT-FAILURE" in result.text
    assert "OLD-FAILURE" not in result.text


def test_new_revision_patch_uses_its_own_passing_automatic_test():
    history = [
        {
            "step": 1,
            "action": {"name": "run_command"},
            "observation": {"success": False, "output": "OLD-FAILURE"},
        },
        {
            "step": 2,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {
                    "changed": True,
                    "path": "src/parser.py",
                    "post_patch_test": {"success": True, "output": "1 passed"},
                },
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "verified_patch"
    assert result.metadata["revision_navigation_cap"] is None
    assert "latest_agent_pytest=passed" in result.text


def test_denied_command_is_not_treated_as_pytest_evidence_for_current_patch():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 2,
            "action": {"name": "run_command", "arguments": {"command": "sed -n 1,20p src/parser.py"}},
            "observation": {
                "success": False,
                "output": "command denied; only pytest is permitted",
                "metadata": {"output_chars": 40, "output_truncated": False},
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_verification"
    assert result.metadata["revision_navigation_cap"] is None
    assert result.metadata["revision_working_set_active"] is False
    assert result.metadata["phase_working_set_active"] is True
    assert result.metadata["phase_working_set_kind"] == "verification"
    assert "latest_agent_pytest=not run for current patch" in result.text


def test_executed_pytest_metadata_is_current_test_evidence():
    history = [
        {
            "step": 1,
            "action": {"name": "read"},
            "observation": {"success": True, "output": "EARLY-SOURCE"},
        },
        {
            "step": 2,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 3,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "src/parser.py:42: AssertionError",
                "metadata": {"return_code": 1, "timed_out": False},
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_revision"
    assert result.metadata["revision_navigation_cap"] == 1
    assert result.metadata["revision_working_set_active"] is True
    assert "latest_agent_pytest=failed" in result.text


def test_denied_command_does_not_supersede_independent_baseline():
    baseline = Snapshot(False, "ORIGINAL-BASELINE", command="pytest -q tests")
    history = [
        {
            "step": 1,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "command denied; only pytest is permitted",
                "metadata": {"output_chars": 40, "output_truncated": False},
            },
        }
    ]

    result = ContextBuilder("repo", "task", baseline=baseline).build_with_metadata(history)

    assert result.metadata["baseline_output_superseded"] is False
    assert "ORIGINAL-BASELINE" in result.text


def test_verification_working_set_keeps_only_current_patch_and_later_events():
    history = [
        {
            "step": 1,
            "action": {"name": "read"},
            "observation": {"success": True, "output": "OLD-NAVIGATION"},
        },
        {
            "step": 2,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "output": "OLD-PATCH",
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 3,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "OLD-FAILURE",
                "metadata": {"return_code": 1, "timed_out": False},
            },
        },
        {
            "step": 4,
            "action": {"name": "read"},
            "observation": {"success": True, "output": "REVISION-EVIDENCE"},
        },
        {
            "step": 5,
            "action": {"name": "apply_patch"},
            "observation": {
                "success": True,
                "output": "CURRENT-PATCH",
                "metadata": {"changed": True, "path": "src/parser.py"},
            },
        },
        {
            "step": 6,
            "action": {"name": "run_command"},
            "observation": {
                "success": False,
                "output": "DENIED-ACTION",
                "metadata": {"output_chars": 13, "output_truncated": False},
            },
        },
    ]

    result = ContextBuilder("repo", "task").build_with_metadata(history)

    assert result.metadata["repair_phase"] == "patch_needs_verification"
    assert result.metadata["phase_working_set_kind"] == "verification"
    assert result.metadata["phase_working_set_pruned"] == 4
    assert result.metadata["history_events_included"] == 2
    assert "CURRENT-PATCH" in result.text
    assert "DENIED-ACTION" in result.text
    assert "OLD-NAVIGATION" not in result.text
    assert "OLD-PATCH" not in result.text
    assert "OLD-FAILURE" not in result.text
    assert "REVISION-EVIDENCE" not in result.text
