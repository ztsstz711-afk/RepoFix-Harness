# Changelog

## Unreleased

- Add localized `old_text`/`new_text` editing to `apply_patch` while preserving full-file creation and replacement.
- Reject missing and ambiguous localized matches before writing, so the model must provide enough surrounding context.
- Keep workspace journaling, hashes, file-count limits, and rollback behavior identical across both edit modes.
- Validate the localized path with a real DeepSeek repair: 1/1 success, 6 requests, 6,450 tokens, and no full-file content sent.

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
