# RepoFix-Harness

面向 Python Repository Bug Repair 的 Coding Agent Harness。输入一个代码仓库和修复任务，真实 LLM 自主选择工具完成 `inspect → pytest → read/search → patch → pytest → finish`；Harness 负责上下文、权限、预算、状态、恢复、追踪和独立评测。

项目刻意聚焦 Python 仓库修复，不做通用聊天助手、multi-agent 或“小型 Codex 全复刻”。

## 实测结果

2026-08-26 使用 `deepseek-v4-flash` 运行五任务隔离回归集：

| 指标 | 结果 |
|---|---:|
| 修复成功率 | 5/5 |
| 期望改动范围命中 | 5/5 |
| Agent 步骤 / API 请求 | 33 / 33 |
| 总 tokens | 41,299 |
| 重试 | 0 |
| 峰值价格保守估算 | $0.01693 |

其中配置合并任务第一次补丁仍然失败，Agent 根据 pytest 反馈再次修改并通过，形成了真实迭代闭环。完整数据见 [DeepSeek benchmark](docs/v0.9-deepseek-results.md)。

五任务是项目自建的小型 deterministic regression suite，用来验证 Harness 闭环和改动范围，不等同于 SWE-bench 或生产级泛化结论。

新增的 package-style 场景使用 `src/` 布局和 4 个相互依赖的业务模块。真实 DeepSeek 运行在 7 次请求内只局部修改 `src/order_pipeline/service.py`，最终 7 项测试通过，详见 [Package scenario result](docs/package-scenario-results.md)。

## 核心能力

- 自主 Agent Loop：模型每轮选择一个结构化 action
- 工具运行时：`list/search/read/apply_patch/run_command/git_diff/git_status`
- `apply_patch` 优先执行唯一匹配的局部替换，避免小改动重传整个文件；创建文件时仍支持完整内容
- 真实 OpenAI-compatible provider，可切换 DeepSeek、Gemini 等服务
- 独立 baseline/final pytest，不接受模型口头宣称“已修复”
- baseline 的命令与压缩后失败输出直接进入首轮 context，模型无需先重复运行完整测试
- 有界 context、工具输出头尾压缩、最近进度摘要
- step/request/token 预算、成本估算、限流与超时重试
- 重复动作检测，阻止无进展循环持续消耗 API
- 仓库路径、控制目录、pytest 参数和改动文件数权限
- 每次写入前保存 run 级原始快照，支持失败或事后回滚
- 回滚前进行路径、备份和结束哈希预检，保护用户后续修改
- checkpoint/resume、逐步 trace、独立 run artifacts
- 隔离 evaluation suite，统计成功率、范围准确率、tokens、成本和失败类型

架构与模块职责见 [Architecture](docs/architecture.md)。

## 快速开始

```powershell
cd <project-path>\RepoFix-Harness
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

配置 DeepSeek（Key 隐藏输入，不写入项目）：

```powershell
.\scripts\setup_deepseek.ps1
```

运行隔离单任务演示：

```powershell
.\scripts\run_demo.ps1
```

直接修复指定仓库：

```powershell
repofix --repo <python-repo> --task "Fix the failing tests" --max-requests 8 --max-tokens 20000
```

为采用特定测试入口的仓库指定 Harness 独立验证命令：

```powershell
repofix --repo <python-repo> --task "Fix the parser bug" --test-command "pytest -q tests/parser"
```

`--test-command` 只接受 pytest 调用，且同一命令会用于 baseline、最终验证和回滚后验证。它也可以通过 `REPOFIX_TEST_COMMAND` 或 evaluation task 的 `test_command` 配置。

启用失败自动回滚：

```powershell
repofix --repo <python-repo> --task "Fix the failing tests" --rollback-on-failure
```

运行模型前单独检查仓库环境（不需要 API Key）：

```powershell
repofix-doctor --repo <python-repo> --test-command "pytest -q tests"
```

预检会检查 pytest、命令安全性、Python/测试文件、项目元数据和 Git。致命问题会生成 `preflight_failed`，并在零模型请求时停止；非标准但可能合法的项目结构只产生 warning。

## 四个命令行入口

```text
repofix       运行单个真实 Agent 修复任务
repofix-eval  在隔离副本中顺序执行 JSON evaluation suite
repofix-runs  列出、查看或安全回滚历史 run
repofix-doctor 在不调用模型的情况下检查仓库运行条件
```

常用操作：

```powershell
repofix-eval --suite evals/regression.json
.\scripts\run_demo.ps1 -Suite evals\package.json
repofix-runs --repo <repo> list
repofix-runs --repo <repo> show latest
repofix-runs --repo <repo> rollback latest
```

如果文件在 Agent 结束后又被修改，普通回滚会拒绝覆盖；只有明确放弃后续修改时才使用 `rollback <run-id> --force`。

## 运行产物

```text
<repo>/.repofix/
├── trace.json                   # latest checkpoint
├── result.json                  # latest terminal result
└── runs/<run_id>/
    ├── trace.json
    ├── result.json
    └── workspace/
        ├── manifest.json        # before/after hash ledger
        └── backups/*.bin        # original file bytes
```

`result.json` 包含任务状态、模型、步骤、token、成本、失败分类、baseline/final pytest、改动文件以及回滚结果。

## 评测场景

`evals/regression.json` 包含五种小型 Bug：错误运算符、字符串规范化、`None` 配置语义、分页边界和跨模块库存判断。`evals/package.json` 进一步提供带 `src/` 布局、Decimal 金额计算以及 pricing/discount/shipping/service 边界的包级场景。每个任务声明隐藏的期望改动范围，但该信息不会进入模型 prompt。

单元测试使用 mock/scripted provider，因此不会产生 API 费用；项目主路径和 `repofix-eval` 始终使用真实 API provider。

## 安全边界与非目标

V1.0 只允许 Agent 读取仓库可见文件、写入仓库普通文件、运行 pytest，以及查看 Git diff/status。它不是完整 OS sandbox，因此不要对不可信仓库授予高权限环境。

当前不包含 LangGraph、multi-agent、MCP、完整 Docker sandbox、SWE-bench/BugsInPy。选择标准库状态机和小模块，是为了让控制流、安全边界和失败行为可以直接审查与面试讲解。

## 文档

- [架构与数据流](docs/architecture.md)
- [演示流程](docs/demo.md)
- [面试讲解指南](docs/interview-guide.md)
- [DeepSeek 配置](docs/deepseek-setup.md)
- [V0.9 回归集设计](docs/v0.9-regression-suite.md)
- [真实 benchmark 结果](docs/v0.9-deepseek-results.md)
- [Package-style 真实验证](docs/package-scenario-results.md)
