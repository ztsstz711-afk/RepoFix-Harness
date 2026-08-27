# Import-aware context paired result

Run date: 2026-08-27  
Model: `deepseek-v4-flash`  
Suite: `evals/import-context.json`  
Execution backend: restricted Docker

The optional-config fixture produces an assertion-only traceback that names `test_config_loader.py` but not the implementation. V1.2 parses `from config_loader import merge_config`, resolves the local module, and centers a bounded snippet on `merge_config` without importing or executing repository code.

Two consecutive runs used the same model, fixture, budgets, and sandbox. The first retained the older generic “inspect before editing” instruction; the second explicitly treated the supplied baseline and source snippets as inspection evidence.

| Metric | Generic instruction | Evidence-aware instruction |
|---|---:|---:|
| Status | success | success |
| Expected scope match | yes | yes |
| API requests | 6 | 3 |
| Total tokens | 9,820 | 5,159 |
| Estimated cost | $0.00395738 | $0.002969 |
| Changed file | `config_loader.py` | `config_loader.py` |

Action paths:

```text
generic:  list → read → read → localized patch → pytest → finish
evidence: localized patch → pytest → finish
```

The evidence-aware run used 50% fewer requests and about 47% fewer tokens. This is a single paired scenario, not a statistically significant benchmark; it demonstrates that context construction and the instruction describing that context must be designed together.

## V1.2 release verification

The final release candidate repeated the evidence-aware three-action path in restricted Docker using 4,663 tokens and an estimated `$0.00235388`. Its evaluation report persisted three context snapshots. The first recorded 2,248 context characters and two selected sources:

- `test_config_loader.py:9`, selected from the pytest traceback;
- `config_loader.py:7`, selected through the local import of `merge_config`.

The second and third snapshots recorded no seeded source files, confirming that automatic snippets were limited to the first model request.
