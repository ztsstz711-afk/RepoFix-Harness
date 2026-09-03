# Changelog

## Unreleased

## 4.7.0 - 2026-09-03

- Surface per-case target-read and non-zero repair-phase deltas in comparison Markdown.
- Add a model-neutral, bounded three-case manifest for native schema-v3 model comparisons.
- Verify Flash and Pro at 3/3 repairs and exact scopes; Pro used 27.27% fewer requests and 38.61% fewer tokens but cost 94.61% more.

## 4.6.0 - 2026-08-31

- Add a bounded three-case Docker gate for native schema-v3 phase telemetry generation.
- Verify 3/3 repairs and exact scopes with 12/24 authorized requests, 22,205 tokens, and no retries.
- Freeze report, manifest, Harness source, source-tree, and Docker runtime fingerprints for the native telemetry result.

## 4.5.0 - 2026-08-30

- Add overall and per-case repair-phase deltas to strict model/thinking report comparisons.
- Surface non-zero phase-count differences and per-case snapshot deltas in comparison Markdown.
- Keep phase deltas optional for historical schema-v1/v2 reports while publishing comparison schema v2.

## 4.4.0 - 2026-08-30

- Add checksum-derived repair-phase telemetry grouped by evaluation case and variant.
- Introduce report schema v3 while retaining validation and resume compatibility for schema v1 and v2.
- Surface grouped snapshot and target-read activation totals in the human-readable evaluation report.

## 4.3.0 - 2026-08-30

- Add report-level repair-phase counts, changed-phase transitions, and target-read grace activations derived from task context snapshots.
- Introduce evaluation report schema v2 with backward-compatible v1 validation and resume support.
- Reject schema-v2 reports whose phase telemetry was altered or no longer matches the underlying task snapshots.

## 4.2.0 - 2026-08-30

- Add a nine-trial cross-project regression gate over three checksum-qualified upstream bug families.
- Verify 9/9 repairs and exact scopes with 43 requests, 103,631 tokens, and no provider retries.
- Confirm the V4.1 target-read grace remains inactive on short stable trajectories and does not add navigation overhead.

## 4.1.0 - 2026-08-30

- Add a one-action target-read grace when the fifth successful navigation action discovers an unread source line.
- Restrict the grace phase to `read` or `apply_patch`, then return to patch-only policy after the read.
- Improve the frozen ItsDangerous Pro gate from 0/3 to 3/3 while reducing requests by 33.33% and tokens by 28.33%.

## 4.0.0 - 2026-08-29

- Add an eighth checksum-qualified upstream bug family from ItsDangerous, including reproducible parent/fix archive preparation and Docker qualification.
- Freeze a one-trial Flash/Pro comparison where only Pro completed, then keep the separate 0/3 Pro stability follow-up instead of promoting the selected success.
- Document the new model-selection counterexample and preserve Flash/non-thinking as the cost-effective default without automatic routing.

## 3.9.0 - 2026-08-29

- Add a frozen three-trial Tomli thinking-mode comparison over the existing checksum-qualified upstream regression.
- Record a 3/3 versus 3/3 result where thinking-high used 39.04% more tokens and cost 95.82% more at conservative peak prices.
- Keep Flash/non-thinking as the default and document that the positive h11 thinking result does not generalize to every difficult repair.

## 3.8.0 - 2026-08-29

- Add request timeout to evaluation identity and reject comparisons with unequal provider wait limits.
- Support strict single-variable comparisons over either model or thinking mode.
- Freeze the first Pro thinking-high comparison on the h11 state-machine case.

## 3.7.0 - 2026-08-29

- Add strict cross-model evaluation report comparison with identity and aggregate validation.
- Freeze Flash versus Pro comparisons on Click and h11.

## 3.6.0 - 2026-08-29

- Add the checksum-qualified Click help-rendering upstream gate and isolated `src/` layout support.

## 3.5.0 - 2026-08-29

- Delegate residual token admission for active phase working sets to providers that explicitly implement a next-action token allowance.
- Keep AgentLoop's conservative historical admission for ordinary contexts and providers without a token-limit interface.
- Record whether each context snapshot used provider-managed admission while preserving the same hard run-level token ceiling.

## 3.4.0 - 2026-08-29

- Add a verification working set that keeps only the current changed patch and later tool events while focused pytest is still required.
- Record a general phase working-set kind and pruning count while preserving the V3.1 revision-specific metadata fields for compatibility.
- Use compact verification context for request admission instead of an obsolete historical-average floor.

## 3.3.0 - 2026-08-29

- Count `run_command` as pytest evidence only when execution metadata proves the command actually ran or timed out.
- Keep denied non-pytest commands in the trace without changing repair phase, revision cap, working-set selection, or baseline freshness.
- Retain compatibility with older checkpoints whose completed pytest events predate execution metadata.

## 3.2.0 - 2026-08-29

- Invalidate focused pytest evidence whenever a later successful patch changes the workspace, so verification state always describes the current code.
- Preserve automatic post-patch test results as fresh evidence from the same edit, including both failed revision feedback and successful verification.
- Reset revision navigation and working-set selection after an untested revision patch instead of carrying a stale failure across code versions.

## 2.4.0 - 2026-08-28

## 2.3.0 - 2026-08-28

- Reject exact-replacement `apply_patch` actions whose `old_text` and `new_text` are identical before they consume an Agent tool step.
- Make zero-result searches explicit evidence misses and force `list/read` after three misses instead of allowing empty searches to create patch readiness.

## 2.2.0 - 2026-08-28

- Bound post-patch and rejected-patch navigation to two successful read/search actions before the phase policy exposes only `apply_patch` again.

## 2.1.0 - 2026-08-28

- Retry one malformed native tool response in native mode before falling back to JSON, with mode-specific correction guidance.
- Allow a separate, recorded patch-phase output ceiling so reasoning models can complete tool arguments without increasing navigation-call output limits.
- Record the exact Python executable and Harness module path in evaluation identity, and make virtual-environment activation explicit in Windows setup instructions.
- Add a portable `auto/enabled/disabled` thinking-mode setting; DeepSeek setup selects non-thinking mode for bounded tool-call reliability and records the choice in evaluation reports.

## 2.0.0 - 2026-08-28

- Add an idempotent Windows project setup script that creates `.venv`, installs editable development dependencies, and optionally builds the Docker pytest image.
- Publish a three-case, nine-trial real-upstream stability gate with honest per-case reliability and failure distributions.
- Refresh architecture, README, and interview guidance to describe native tools, repair phases, CLI presentation, and current model limitations.

## 1.9.0 - 2026-08-28

- Add a human-readable single-run progress view with repair phase, remaining request/token budget, action targets, focused patch verification, and Provider retry counts.
- Replace the one-line final output with an outcome-first summary covering baseline-to-final tests, changed files, usage, cost, backend, failure/rollback details, and the result artifact path.
- Add `--json` for a progress-free machine-readable final RunState while retaining `--quiet` for a concise human summary.
- Hide Git actions from the Provider when preflight determines the target is not a Git worktree.

## 1.8.0 - 2026-08-28

- Enforce phase-aware action availability across native Function Calling and JSON fallback instead of relying on prompt guidance alone.
- Restrict `patch_due` to `apply_patch`, verified repairs to diff/status/finish, and revision/verification phases to the smallest relevant tool subsets.
- Reject model actions outside the current repair phase even if a compatible endpoint returns an undeclared tool call.
- Validate the phase policy once across three checksum-qualified upstream bugs: two exact-scope full-suite repairs, including the first designated Tomli success, within 26 of 36 authorized requests.

## 1.7.0 - 2026-08-28

- Replace prompt-example type inference with explicit action argument schemas, including descriptions, numeric bounds, and mutually exclusive localized/full-file patch modes.
- Persist bounded Provider format diagnostics even when a later retry returns a valid action.
- Add deterministic repair phases and next-action guidance so accumulated search/read evidence transitions toward a minimal patch and verified patches transition toward finish.
- Add an offline Tomli-style facade-to-parser repair trajectory covering baseline seeding, localized patching, automatic focused verification, and final acceptance.
- Stop duplicating the full action contract in native-tool system prompts; inject it only when a failed native response falls back to JSON mode.
- Escalate five successful navigation actions without a change from `ready_to_patch` to `patch_due`, explicitly directing the model to patch from observed exact text.
- Label format diagnostics by native/JSON/text mode and report empty compatible responses explicitly.

## 1.6.0 - 2026-08-28

- Persist compact read-range and search-query navigation memory in every model context and context snapshot.
- Skip oversized middle observations while selecting bounded history so smaller, older search and patch evidence can remain visible.
- Add structured read/search telemetry for file ranges, total lines, query scope, match counts, and truncation.
- Add optional Harness-owned focused pytest feedback after each changed patch, while keeping full-suite final acceptance independent.
- Follow actually called module attributes through up to three local facade/re-export files when seeding failure context, scoped to the traceback's failing function and parsed without importing repository code.
- Prefer provider-native single-tool calls generated from the central action registry, with schema validation and automatic fallback to JSON mode for compatible endpoints that do not return a valid tool call.
- Preserve the last provider format error when a request budget interrupts a retry and select the first valid action from compatible providers that emit parallel tool calls.
- Pass the remaining run-level token allowance into the Provider and deny an internal format retry whose estimated request would exceed it, preventing retries inside one Agent step from bypassing the Harness admission budget.

## 1.5.0 - 2026-08-28

- Add a checksum-pinned preparation workflow for three real upstream bug-fix commits from more-itertools and Tomli.
- Build each V1.5 buggy workspace from the fix commit's parent implementation plus only the upstream regression test, never the upstream repair patch.
- Add a Docker-only, 36-request-authorized external evaluation manifest with focused feedback tests, full-suite final acceptance, and hidden expected file scope.
- Separate the fast baseline/iteration pytest command from an optional full-suite final command across CLI, environment configuration, checkpoints, preflight, rollback, and evaluation reports.
- Bound repository listings to 4,000 characters and prioritize shallow source paths before deep fixture trees, preserving omitted-file counts in tool metadata.
- Account for every malformed-response attempt when provider format retries are exhausted, so request, token, retry, and cost reports cannot silently undercount failed calls.
- Allow up to four bounded format-correction retries and independently verify an existing patch if the provider's next action remains malformed.
- Request provider-native JSON output by default, include a valid action example, expose the mode in experiment metadata, and retain an environment-controlled fallback for older compatible endpoints.
- Fall back to prompt-constrained text output within the current action after an empty JSON-mode response, avoiding repeated empty retries while preserving usage accounting and request limits.
- Guide repository navigation toward search plus narrow reads, and calibrate the Tomli token ceiling from an observed three-action repair tail without increasing its 12-request authorization.

## 1.4.0 - 2026-08-27

- Expand a traceback-selected test's imported facade by one additional local call edge, attaching only repository functions actually called by the selected implementation function.
- Keep call-aware context extraction AST-only, bounded by the existing file/character limits, and non-recursive.
- Validate the targeted change over six interleaved DeepSeek Docker trials: both variants repaired 3/3 with exact scope, while call-aware context used 50% fewer requests and 52.8% fewer tokens on average.

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
