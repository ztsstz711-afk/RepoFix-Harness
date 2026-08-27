# Changelog

## Unreleased

- Add localized `old_text`/`new_text` editing to `apply_patch` while preserving full-file creation and replacement.
- Reject missing and ambiguous localized matches before writing, so the model must provide enough surrounding context.
- Keep workspace journaling, hashes, file-count limits, and rollback behavior identical across both edit modes.
- Validate the localized path with a real DeepSeek repair: 1/1 success, 6 requests, 6,450 tokens, and no full-file content sent.
- Add a configurable Harness-owned pytest command across CLI, checkpoints, evaluation suites, and post-rollback verification.
- Reject non-pytest verification commands before the first model request, and reject resume when the verification contract changed.
- Include the bounded independent baseline command and pytest output in every model context, avoiding a mandatory duplicate test run.
- Mark repository content, pytest output, and tool observations as untrusted prompt data.
- Real-model validation completed the demo in five requests with localized editing and persisted baseline/final commands.
- Separate immutable tool/control instructions into the system message and untrusted repository context into the user message.
- Validate the two-role provider path against DeepSeek with a five-request successful repair.
- Add persisted, model-free repository preflight checks for pytest, command safety, Python/test files, project metadata, and Git availability.
- Add `repofix-doctor` so environment problems can be diagnosed without an API key or model request.
- Add a package-style order pipeline scenario with `src/` layout, Decimal business logic, and cross-module data flow.
- Validate the package scenario with DeepSeek: 1/1 success, exact change scope, 7 requests, 13,743 tokens, and an estimated $0.00503 cost.
- Add local and Docker pytest execution backends with a minimal pinned sandbox image.
- Restrict Docker test runs with no network, a read-only repository/root filesystem, dropped capabilities, no-new-privileges, tmpfs, and CPU/memory/PID limits.
- Persist the execution backend and image through settings, CLI, checkpoints, resume validation, and evaluation suites.
- Complete a real DeepSeek package repair with all pytest execution routed through the restricted Docker backend.
- Fail Docker preflight before model use when the daemon, image, or container pytest is unavailable.
- Add next-request token admission estimates and allow independently verified repairs to complete safely at a budget boundary.
- Persist backend, image, and timeout across checkpoints and post-rollback verification.
- Add a checksum-pinned, reproducible external h11 v0.16.0 benchmark and complete it in 17,287/20,000 tokens.
- Scrub provider keys and common credential variables from local pytest and Git subprocess environments.
- Disable repository-configured external diff, text conversion, fsmonitor, global/system Git config, and optional locks for Git inspection tools.
- Add real Docker probes for network isolation, read-only mounts, secret absence, writable tmpfs, timeout, and forced container cleanup.
- Bound each compatible-provider completion to 2,048 output tokens by default.
- Enforce the remaining request allowance inside provider format/transient retries so internal retries cannot overspend the run budget.
- Preserve Docker execution metadata in baseline/final snapshots and aggregate evaluation reports.
- Reject explicit empty test commands and non-positive command timeouts instead of silently replacing them with defaults.
- Preserve timeout observations when forced Docker cleanup fails and record cleanup diagnostics in execution metadata.

## 1.0.0

- Freeze the Python repository repair scope after a successful real five-task benchmark.
- Restructure the README around outcomes, architecture, safety, and reproducible usage.
- Add architecture and interview guides with explicit claims and limitations.
- Add a budgeted one-command real-model demo that always uses an isolated repository copy.
- Document the three CLIs, run artifact layout, trust boundaries, and V1.0 non-goals.

## 0.9.0

- Expand evaluation from two toy tasks to five complementary Python bug scenarios.
- Add optional-config, one-based-pagination, and package-level inventory fixtures.
- Add task tags and hidden expected-change scopes to evaluation manifests and reports.
- Report both test success rate and changed-file scope accuracy.
- Validate every fixture starts with a failing baseline and passes through isolated scripted repairs.
- Add a hidden-input DeepSeek V4 Flash setup script with conservative cost-estimation rates.
- Validate the real five-task DeepSeek benchmark with 5/5 repairs and 5/5 change-scope matches.

## 0.8.0

- Add `repofix-runs list/show/rollback` for local run inspection and recovery.
- Record the Agent's final file hash and refuse to overwrite later user edits by default.
- Add an explicit `--force` override for intentional conflict recovery.
- Preflight every path, end hash, and backup before a multi-file rollback starts.
- Keep the latest-run pointer unchanged when an older run is inspected or restored.
- Reject unsafe run IDs before resolving artifact paths.

## 0.7.0

- Snapshot original file bytes before the first real Agent write in each run.
- Restore existing files atomically and remove Agent-created files on optional failure rollback.
- Limit the number of distinct changed files without counting no-op writes.
- Persist rollback files, rollback errors, and post-rollback pytest results.
- Reuse the same workspace journal when a checkpoint is resumed.

## 0.6.0

- Stop repeated identical actions before they create an unbounded agent loop.
- Reset repetition tracking after a real file modification.
- Bound every tool observation while preserving both diagnostic headers and summaries.
- Add compact context progress summaries for changed files and the latest agent pytest result.
- Guarantee the final model context stays within its configured character budget.
- Validate the complete V0.6 loop with a successful real Gemini repair.

## 0.5.0

- Add request, token, and step budgets with resumable budget-exhausted results.
- Track format and transient retry counts alongside model requests and tokens.
- Estimate run and suite cost using configurable input, output, and cached-input prices.
- Classify provider, verification, and budget failures in run and aggregate reports.
- Add CLI budget flags and suite-level budget overrides.

## 0.4.0

- Add JSON evaluation suites and an isolated sequential runner.
- Add the `repofix-eval` CLI and two-task smoke suite.
- Aggregate success rate, steps, duration, requests, tokens, and changed files.
- Preserve per-task run artifacts without mutating source repositories.
- Validate the real Gemini smoke suite with 2/2 successful repairs.

## 0.3.0

- Preserve trace and result artifacts for every run ID.
- Track actual Agent writes with before/after SHA-256 hashes.
- Stream baseline, model request, and tool progress through the CLI.
- Retry malformed model actions with schema feedback.
- Add a multi-file repair scenario and real Gemini validation.

## 0.2.0

- Centralize tool schemas and argument validation.
- Add repository path, control-directory, and pytest command permissions.
- Run independent baseline and final pytest evaluation.
- Generate a structured `result.json` and reject unverified finishes.

## 0.1.0

- Add the OpenAI-compatible provider, Agent Loop, bounded context, trace, checkpoint/resume, toy repository, and mock tests.
