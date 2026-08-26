# Changelog

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
