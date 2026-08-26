# RepoFix-Harness

面向 Python Repository Bug Repair 的 Coding Agent Harness。输入一个仓库和修复任务，Agent 通过真实 LLM 自主 inspect、运行测试、读取代码、修改代码并验证结果。

## V0.4 当前能力

- Agent loop：模型选择下一步 action，直到完成或达到步数预算
- 基础工具：list/search/read/apply_patch/run_command/git diff/status
- 有界 context、逐步 trace、checkpoint/resume
- 请求与 token 用量统计、429/5xx/超时重试
- 单一工具注册表与参数校验
- 仓库边界、控制目录和 pytest 命令权限
- Harness 独立执行 baseline/final pytest
- 生成 `.repofix/trace.json` 与 `.repofix/result.json`
- 每个 run 独立保存在 `.repofix/runs/<run_id>/`
- apply_patch 前后内容哈希与 Agent 改动文件账本
- CLI 实时输出 baseline、模型请求和工具步骤
- 模型 JSON 格式错误自动纠正重试
- JSON evaluation suite 与隔离临时仓库
- 顺序批量评测、成功率/步骤/token/耗时聚合
- 每个评测任务保留独立 trace/result artifacts
- OpenAI-compatible provider：环境变量 `REPOFIX_BASE_URL`、`REPOFIX_API_KEY`、`REPOFIX_MODEL`
- 可运行 toy buggy repo 与 mock provider 单测

暂不包含 LangGraph、multi-agent、MCP、Docker sandbox、SWE-bench/BugsInPy。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:REPOFIX_API_KEY="your-key"
$env:REPOFIX_MODEL="your-model"
python -m repofix.cli --repo examples/toy_repo --task "Fix the failing tests"
```

中断后可使用相同任务继续：

```powershell
python -m repofix.cli --repo examples/toy_repo --task "Fix the failing tests" --resume
```

运行两任务 smoke 评测：

```powershell
repofix-eval --suite evals/smoke.json
```

评测在临时副本中顺序执行，不修改 `examples/` 下的源仓库；输出默认写入 `eval-results/`。

默认 provider 是真实 OpenAI-compatible provider；单测使用 mock provider，不会发起网络请求。
如果使用其他兼容服务，同时设置 `REPOFIX_BASE_URL`。可参考 `.env.example`，但不要把真实密钥写入 Git。

### Gemini 配置

在 Google AI Studio 创建并复制 API Key 后运行：

```powershell
.\scripts\setup_gemini.ps1
```

脚本会隐藏密钥输入，并将 Gemini 的 API Key、兼容接口地址和模型保存到当前 Windows 用户环境变量；密钥不会写入项目文件或 Git。
V0.4 已使用 `gemini-3.5-flash-lite` 完成 2/2 smoke suite 验证，后续可仅通过环境变量切换到 DeepSeek。Gemini 2.5 Flash 系列已经不再向新用户提供生成请求。

## 目录

`repofix/` 是 harness 核心；`examples/toy_repo/` 是单文件 Bug；`examples/multi_file_repo/` 用于验证跨文件 search/read/edit；`tests/` 验证工具、provider、loop 和 evaluator。

## V0.1 技术判断

可行性高：工具调用和状态机都是本地 Python 能力，真实 LLM 只负责选择动作和生成 patch。风险集中在模型输出格式、命令权限和上下文增长，第一版通过 JSON schema、允许命令白名单、步数预算和 trace 缓解。
