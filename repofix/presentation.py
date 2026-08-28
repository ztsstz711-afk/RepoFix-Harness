from pathlib import Path


def format_progress(state, event: dict) -> list[str]:
    event_type = event["type"]
    if event_type == "preflight":
        warnings = sum(check.status == "warning" for check in state.preflight.checks)
        lines = [
            f"[preflight] {'PASS' if event['success'] else 'FAIL'}"
            f"  warnings={warnings}"
        ]
        lines.extend(
            f"  - {check.name}: {check.message}"
            for check in state.preflight.checks
            if check.status == "fail"
        )
        return lines
    if event_type == "baseline":
        return [
            f"[baseline] {'PASS' if event['success'] else 'FAIL'}"
            f"  backend={event['execution_backend']}"
        ]
    if event_type == "model_request":
        remaining_requests = event.get("remaining_requests")
        remaining_tokens = event.get("remaining_tokens")
        budget = (
            f" remaining_requests={remaining_requests}"
            if remaining_requests is not None
            else ""
        )
        if remaining_tokens is not None:
            budget += f" remaining_tokens={remaining_tokens}"
        return [
            f"[step {event['step']:02d}] MODEL"
            f"  phase={event.get('repair_phase', 'unknown')}"
            f" context={event.get('context_chars', 0)} chars"
            f" seeded_sources={event.get('seeded_sources', 0)}{budget}"
        ]
    if event_type == "step":
        action = event.get("action", {})
        name = action.get("name")
        if not name:
            return [f"[step {event['step']:02d}] ERROR  {event.get('error', 'unknown')}"]
        observation = event.get("observation")
        status = ""
        if observation is not None:
            status = "PASS" if observation.get("success") else "FAIL"
        arguments = action.get("arguments", {})
        target = (
            arguments.get("path")
            or arguments.get("query")
            or arguments.get("command")
            or ""
        )
        line = f"[step {event['step']:02d}] {name.upper()}"
        if status:
            line += f"  {status}"
        if target:
            line += f"  {target}"
        lines = [line]
        post_patch = (observation or {}).get("metadata", {}).get("post_patch_test")
        if isinstance(post_patch, dict):
            lines.append(
                "           focused pytest "
                + ("PASS" if post_patch.get("success") else "FAIL")
            )
        diagnostics = event.get("provider_diagnostics", [])
        if diagnostics:
            lines.append(f"           provider retries={len(diagnostics)}")
        return lines
    if event_type == "budget":
        outcome = "repair verified" if event.get("repair_verified") else "stopped"
        return [f"[budget] {outcome}: {event['failure_kind']} - {event['error']}"]
    if event_type == "stalled":
        return [f"[stalled] {event['failure_kind']}: {event['error']}"]
    if event_type == "rollback":
        return [f"[rollback] restored {', '.join(event['files'])}"]
    if event_type == "rollback_error":
        return [f"[rollback] FAIL: {event['error']}"]
    return []


def format_run_summary(state) -> str:
    baseline = getattr(state.evaluation.baseline, "success", None)
    final = getattr(state.evaluation.final, "success", None)
    baseline_text = _test_status(baseline)
    final_text = _test_status(final)
    changed = state.evaluation.changed_files
    result_path = Path(state.repo) / ".repofix" / "result.json"
    lines = [
        "",
        "=== RepoFix Result ===",
        f"Status: {state.status.upper()}",
        f"Tests: baseline {baseline_text} -> final {final_text}",
        f"Changed files: {', '.join(changed) if changed else 'none'}",
        f"Steps: {state.step}",
        (
            f"Model usage: {state.usage.requests} requests, "
            f"{state.usage.total_tokens} tokens, {state.usage.retries} retries"
        ),
        f"Estimated cost: ${state.estimated_cost_usd:.6f}",
        f"Backend: {state.execution_backend}",
    ]
    if state.summary:
        lines.append(f"Summary: {state.summary}")
    if state.failure_kind:
        lines.append(f"Failure: {state.failure_kind} - {state.error}")
    if state.evaluation.rollback_performed:
        lines.append(
            "Rollback: restored " + ", ".join(state.evaluation.rollback_files)
        )
    lines.append(f"Result JSON: {result_path}")
    return "\n".join(lines)


def _test_status(value: bool | None) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "NOT RUN"
