# Package-style repair result

Run date: 2026-08-27  
Model: `deepseek-v4-flash`  
Suite: `evals/package.json`

## Scenario

The repository uses a `src/` package layout and separates order models, merchandise pricing, loyalty discounts, shipping policy, and quote orchestration. The failing behavior incorrectly included shipping fees in the amount eligible for a loyalty discount.

## Result

| Metric | Value |
|---|---:|
| Preflight | passed |
| Baseline | 1 failed, 6 passed |
| Final | 7 passed |
| API requests | 7 |
| Execution backend | restricted Docker |
| Total tokens | 14,868 |
| Estimated cost | $0.00579018 |
| Changed file | `src/order_pipeline/service.py` |
| Expected scope match | yes |
| Patch mode | localized |

Action path:

```text
list → read → read → read → apply_patch → run_command → finish
```

The evaluator ran against an isolated copy and left the source fixture in its original failing state. Baseline, Agent-requested pytest, and final verification all ran in the restricted Docker backend. This remains a controlled project-authored scenario, not evidence of performance on arbitrary production repositories.
