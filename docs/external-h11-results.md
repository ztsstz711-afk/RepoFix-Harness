# External h11 repair result

Source: `python-hyper/h11` tag `v0.16.0`  
Archive SHA-256: `6CC72241F709C9400E5DD44252A519906C842EB6EDEC4E01A70DA148A1145FC8`  
Run date: 2026-08-27  
Model: `deepseek-v4-flash`

The preparation script downloads the fixed upstream archive, verifies its checksum, keeps an untouched clean reference, and injects one HTTP version boundary regression into a separate ignored workspace.

| Stage | Result |
|---|---:|
| Clean upstream baseline | 78 passed |
| Injected regression baseline | 2 failed, 76 passed |
| Final isolated verification | 78 passed |
| Expected change scope | `h11/_headers.py` only |
| Patch mode | localized |
| Model actions | 5 |
| API requests | 5 |
| Tokens | 17,287 of a 20,000 budget |
| Retries | 0 |
| Estimated cost | $0.007092 |

All pytest executions used the restricted Docker backend with networking disabled and the repository mounted read-only. The Agent restored the strict HTTP/1.0 comparison while preserving HTTP/1.1 `Expect: 100-continue` behavior.

This benchmark is an injected regression over real third-party source, not an upstream h11 issue and not a SWE-bench result.
