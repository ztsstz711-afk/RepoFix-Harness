# Provider Capacity Plan

## Decision

Use the Gemini free tier for V0.1 development and milestone smoke tests. Use DeepSeek's paid API when running repeated real-repository evaluations. Do not upgrade Gemini solely to remove the free-tier request limit unless Gemini-specific quality is required.

## Evidence and definitions

- One RepoFix agent step currently equals one model API request.
- The verified toy repair used 7 model decisions and completed the full fail-read-edit-pass loop.
- The configured Gemini model returned a project/model quota of 5 requests per minute.
- Mock-provider unit tests do not call an external model and therefore consume no API quota.
- Token volumes below are planning estimates, not billing records. They assume the current cumulative-context implementation and no cache discount.

## Capacity simulation

| Workload | Model requests | Minimum time at 5 RPM | Practical elapsed time | Gemini free-tier fit |
|---|---:|---:|---:|---|
| Toy bug | 6-8 | 1.2-1.6 min | 2-4 min | Good |
| Small repository bug | 12-20 | 2.4-4 min | 4-8 min | Usable but slow |
| Medium repository bug | 25-40 | 5-8 min | 10-20 min | Poor for iteration |
| Evaluation batch: 20 small tasks | 240-400 | 48-80 min | 2-4 hours | Not suitable |

Practical time includes model latency, test execution, and rate-limit window alignment. Daily quotas are account/model-specific and must be checked in Google AI Studio; only the observed 5 RPM limit is treated as verified here.

## Conservative DeepSeek cost simulation

Using the published `deepseek-chat` rates of $0.27 per 1M uncached input tokens and $1.10 per 1M output tokens:

| Workload | Estimated total input | Estimated total output | Estimated cost |
|---|---:|---:|---:|
| Toy bug | 15k-30k | 1k-3k | $0.005-$0.011 |
| Small repository bug | 100k-300k | 5k-10k | $0.033-$0.092 |
| Medium repository bug | 500k-1.5M | 10k-30k | $0.146-$0.438 |

Actual DeepSeek cost may be lower when repeated prompt prefixes receive cache-hit pricing. Cost can be higher if repository output or command traces are allowed to grow without context pruning.

## Switching rule

Stay on Gemini free while all three conditions hold:

1. Real-model runs are milestone smoke tests rather than every-test runs.
2. No more than two or three real repair tasks need to run in one development session.
3. Waiting several minutes for one task does not block development.

Switch to DeepSeek when any condition fails, especially for benchmark-style evaluation, repeated prompt tuning, or demos requiring predictable latency. Keep both providers behind the same OpenAI-compatible interface and switch with environment variables.

## Next measurements

Record per run: model requests, input/output tokens, elapsed time, retries, tool failures, final test result, and estimated cost. Revisit this decision after at least 20 real tasks because the current evidence contains only a toy repair.

## Sources

- Google Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- DeepSeek API pricing: https://api-docs.deepseek.com/quick_start/pricing-details-usd
