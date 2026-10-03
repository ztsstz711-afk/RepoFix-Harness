# Frozen upstream V1.5 current run

## Result

On 2026-10-03, RepoFix-Harness ran the unchanged
`evals/upstream-bugs-v1.5.json` manifest under Docker. The run completed with
`2/3` independently accepted repairs.

| Task | Baseline | Final pytest | Changed-file oracle | Outcome |
|---|---:|---:|---:|---|
| more-itertools sliced negative size | fail | pass | pass | accepted |
| more-itertools running min/max stability | fail | pass | pass | accepted |
| tomli dotted-key part limit | fail | fail | pass | request budget exhausted |

The manifest authorizes at most 36 requests. This run used 29 requests and
76,152 total tokens. The third task stopped at its fixed 12-request ceiling;
it was not retried with a larger budget or replaced with another task.

## Reproducibility anchors

- Manifest SHA-256:
  `20b54d79b5b7f56787fa0d7e4751dc54e1576de50ea816e27e3e86e1b5bdd03e`
- Harness source SHA-256:
  `f1a699545b8f3a7fc11b02adc912a2b8355e40c31e967e0398602c31c9fd2f60`
- Final report SHA-256:
  `2996b1696a8c356c24128845fc1b9766cf65a688eac9290d47dbda8e6c360e9a`
- Execution backend: Docker Linux Engine 29.8.0 with the task-defined pytest image.

The original report remains local under
`eval-results/upstream-bugs-v1.5-20261003-dockerready/` and is intentionally
not published. The evidence supports only this frozen three-task run; it does
not establish a general coding-agent repair rate.
