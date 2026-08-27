# Changelog

## Unreleased

- Expand a traceback-selected test's imported facade by one additional local call edge, attaching only repository functions actually called by the selected implementation function.
- Keep call-aware context extraction AST-only, bounded by the existing file/character limits, and non-recursive.

## 1.3.0 - 2026-08-27

- Add an explicit failure-context switch across environment settings, CLI, checkpoints, Agent Loop, and evaluation tasks.
- Add bounded `repetitions` and named `variant` fields to evaluation manifests, with interleaved trial execution and collision-safe artifact IDs.
- Aggregate per-variant success/scope rates plus total, mean, median, minimum, and maximum requests, tokens, steps, and estimated cost.
- Validate context-on versus context-off over six DeepSeek Docker trials: both variants repaired 3/3 with exact scope, while context-on used 50% fewer requests and about 50.4% fewer tokens.
- Add case-aware paired experiment validation, matched success outcomes, and per-pair request/token/step/cost deltas.
- Isolate unexpected runner failures per trial and atomically persist a complete partial `progress.json` after every result.
- Fingerprint the exact evaluation manifest and copied source trees with SHA-256 for reproducible report comparisons.
- Resume interrupted suites in the original interleaved order, skipping completed trials only after report schema, model metadata, manifest, source, and task fingerprints match.
- Generate a concise Markdown report beside every completed evaluation JSON, including variant, paired, per-case, failure, and reproducibility summaries.
- Add an exact two-sided paired sign test for request, token, step, and cost direction, excluding tied trial pairs.
- Validate aggregate counts, usage, costs, scope, and failures before publishing a final report.
- Re-hash every copied trial workspace before provider creation and abort the suite if a source fixture changed after manifest loading.
- Add a suite-level request authorization gate that expands every task limit by repetitions and rejects missing or over-budget manifests before provider creation.
- Reject zero, negative, boolean, and string-coerced task limits so `0` cannot silently mean unlimited inside a budgeted manifest.
- Persist provider model, output cap, and pricing inputs; validate actual task model counts and require identical metadata on resume.
- Preserve structured preflight checks per trial and aggregate Docker daemon/image/pytest fingerprints so mutable image tags remain distinguishable.
- Fingerprint the installed Harness version and exact Python/pyproject source bytes as part of strict experiment identity.
- Expand the context experiment to five bug shapes and 30 DeepSeek Docker trials: both variants repaired 15/15 with exact scope; context-on reduced mean requests by 23.81% and mean tokens by 22.80%, but increased tokens on 4 of 15 matched pairs.
- Pass the final V1.3 DeepSeek Docker release gate with 6/6 repairs and exact scope, using 26/36 authorized requests and producing validated JSON/Markdown reports with immutable runtime fingerprints.

## 1.2.0 - 2026-08-27

- Seed the first model request with bounded, line-numbered repository snippets referenced by the independent pytest baseline.
- Ignore traceback paths outside the target repository and all protected control directories, deduplicate files, and omit the snippets after the first model action.
- Validate the traceback-aware path with DeepSeek in restricted Docker: 1/1 repair, exact file scope, 4 requests, and 6,701 tokens.
- Expand traceback-referenced test files through one hop of local Python imports, supporting repository-root, `src/`, and relative package layouts without importing or executing repository code.
- Center imported snippets on the referenced function, class, or assigned symbol while ignoring external modules and recursive dependencies.
- Treat supplied baseline/snippets as completed inspection evidence; in a paired DeepSeek Docker run this reduced the optional-config path from 6 to 3 requests and from 9,820 to 5,159 tokens.
- Persist per-step context snapshots outside Agent history, including selected relative files, selection reasons, source lines, snippet sizes, history omission counts, and total character budget usage.
- Surface context size and seeded-source counts in CLI progress and include the structured snapshots in evaluation task reports while retaining legacy checkpoint compatibility.
- Complete the release regression with DeepSeek in restricted Docker: exact-scope repair in 3 requests and 4,663 tokens, with all three context snapshots persisted in the report.

## 1.1.0 - 2026-08-27

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
