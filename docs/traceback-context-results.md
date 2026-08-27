# Traceback-aware context result

Run date: 2026-08-27  
Model: `deepseek-v4-flash`  
Suite: `evals/traceback-context.json`

The scenario raises a `KeyError` inside `profile.py`, allowing the independent baseline traceback to reference the implementation rather than only the failing assertion. RepoFix safely attached a bounded, line-numbered source snippet to the first model context.

| Metric | Value |
|---|---:|
| Baseline | 1 failed, 1 passed |
| Final | 2 passed |
| API requests | 4 |
| Total tokens | 6,701 |
| Estimated cost | $0.00375578 |
| Execution backend | restricted Docker |
| Changed file | `profile.py` |
| Expected scope match | yes |
| Patch mode | localized |

Action path:

```text
read profile.py → localized apply_patch → pytest → finish
```

The source fixture remained buggy because the evaluation runner operated on an isolated copy. This one-task result validates the V1.2 context path; it is not a broad accuracy benchmark.
