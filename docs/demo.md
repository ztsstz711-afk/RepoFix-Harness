# Demo

## One-command isolated demo

After installing the project and configuring a provider:

```powershell
.\scripts\run_demo.ps1
```

Fresh Windows setup can be completed with:

```powershell
.\scripts\setup_project.ps1 -BuildSandbox
.\.venv\Scripts\Activate.ps1
.\scripts\setup_deepseek.ps1
```

The script runs one real-model task with an eight-request and 12,000-token ceiling. `EvaluationRunner` copies `examples/toy_repo` to a temporary workspace, so the source fixture remains buggy and reusable.

## What to point out during the demo

1. Baseline pytest fails before the first model request.
2. The model chooses each action; the script does not encode the repair.
3. `apply_patch` records before/after SHA-256 values and a recovery snapshot.
4. Agent-requested pytest provides feedback, but Harness still runs its own final pytest after finish.
5. The final line shows success, expected change-scope match, tokens, estimated cost, and report path.

Open the generated `report.json`, then the task's `runs/toy-add-demo/result.json` to show the complete trace.

## Full benchmark

```powershell
repofix-eval --suite evals/regression.json
```

The five-task run makes roughly 30–40 model requests based on the V0.9 benchmark. Use it when demonstrating aggregate evaluation; use `run_demo.ps1` for a quick interview walkthrough.
