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

V1.1 又完成了两次全部测试均在受限 Docker 中执行的真实闭环：package-style 场景使用 7 次请求、14,868 tokens；基于第三方 h11 v0.16.0 源码的注入回归使用 5 次请求、17,287 tokens，从 `2 failed, 76 passed` 修复到 `78 passed`，且只改动预期文件。后者详见 [External h11 result](docs/external-h11-results.md)。

V1.2 开始加入 traceback-aware context：Harness 从独立 baseline 中提取仓库内源码位置，将有界片段只注入首轮请求。专用场景的真实 DeepSeek + Docker 验证以 4 次请求、6,701 tokens 完成局部修复，详见 [Traceback context result](docs/traceback-context-results.md)。

对于 traceback 只指向测试断言的场景，V1.2 会通过一跳本地 import 找到实现符号。一次同模型、同 fixture 的配对验证把动作路径从 6 请求缩短到 3 请求、tokens 从 9,820 降到 5,159；这是单场景工程验证而非统计性 benchmark，详见 [Import context result](docs/import-context-results.md)。

V1.2 正式发布回归继续保持 3 请求路径，使用 4,663 tokens，并在 evaluation report 中持久化了三轮 context snapshot；首轮明确记录 `test_config_loader.py` 来自 traceback、`config_loader.py` 来自 local import。

## 核心能力

- 自主 Agent Loop：模型每轮选择一个结构化 action
- 工具运行时：`list/search/read/apply_patch/run_command/git_diff/git_status`
- `apply_patch` 优先执行唯一匹配的局部替换，避免小改动重传整个文件；创建文件时仍支持完整内容
- 真实 OpenAI-compatible provider，可切换 DeepSeek、Gemini 等服务
- 独立 baseline/final pytest，不接受模型口头宣称“已修复”
- baseline 的命令与压缩后失败输出直接进入首轮 context，模型无需先重复运行完整测试
- 首轮 context 自动附带 pytest traceback 引用的仓库源码片段；若只命中测试文件，会通过一跳本地 import 定位实现符号，同时过滤外部路径与控制目录
- 有界 context、工具输出头尾压缩、最近进度摘要
- 每步持久化 context 选择元数据，记录自动选中文件、原因、行号与字符预算，但不重复保存源码正文
- step/request/token 预算、成本估算、限流与超时重试
- 重复动作检测，阻止无进展循环持续消耗 API
- 仓库路径、控制目录、pytest 参数和改动文件数权限
- 每次写入前保存 run 级原始快照，支持失败或事后回滚
- 回滚前进行路径、备份和结束哈希预检，保护用户后续修改
- checkpoint/resume、逐步 trace、独立 run artifacts
- 隔离 evaluation suite，统计成功率、范围准确率、tokens、成本和失败类型
- evaluation 支持重复 trial、命名 variant、交错 A/B 执行及请求/token/成本分布统计
- 配对实验按 case + trial 比较成功结果与资源差值，并记录 manifest/fixture SHA-256
- 配对资源指标附带 better/tied/worse 计数和不依赖第三方统计库的双侧精确符号检验
- 每个 trial 后原子更新 `progress.json`；单次 runner 异常被隔离，后续任务继续执行
- 完成时同时生成机器可读 `report.json` 和可直接审阅的 `report.md`
- 发布报告前重算聚合完整性；每次实际复制后重验 source 指纹，禁止中途混入变化的 fixture
- 受限 Docker pytest 后端：禁网、只读仓库、无提权并限制 CPU、内存和进程数

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

使用受限 Docker 容器执行所有 pytest：

```powershell
.\scripts\build_sandbox.ps1
repofix --repo <python-repo> --task "Fix the failing tests" --execution-backend docker
```

Docker backend 默认禁用网络、只读挂载仓库、丢弃 capabilities、禁止提权，并限制 CPU、内存和进程数。模型仍在 Harness 中决策，只有测试代码进入容器执行。

Local backend 仅用于可信仓库；它会移除 `REPOFIX_*` 以及常见 key/token/password/credential 环境变量，但无法提供文件系统隔离。外部仓库应使用 Docker backend。单次模型响应默认限制为 2,048 output tokens，可通过 `REPOFIX_MAX_OUTPUT_TOKENS` 调整。

启用失败自动回滚：

```powershell
repofix --repo <python-repo> --task "Fix the failing tests" --rollback-on-failure
```

运行模型前单独检查仓库环境（不需要 API Key）：

```powershell
repofix-doctor --repo <python-repo> --test-command "pytest -q tests"
```

Docker 模式预检：

```powershell
repofix-doctor --repo <python-repo> --test-command "pytest -q tests" --execution-backend docker
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

`result.json` 包含任务状态、模型、步骤、token、成本、失败分类、baseline/final pytest、改动文件、回滚结果以及每次模型调用的 context snapshot。snapshot 记录上下文长度、历史裁剪和自动源码选择依据，不会在 Agent history 中制造额外事件。

Evaluation 输出目录额外包含逐 trial 的 `runs/`、中断续跑使用的 `progress.json`、完整聚合数据 `report.json`，以及自动生成的 `report.md`。Markdown 只渲染稳定的摘要字段，原始任务与 trace 仍以 JSON 为准。

## 评测场景

`evals/regression.json` 包含五种小型 Bug：错误运算符、字符串规范化、`None` 配置语义、分页边界和跨模块库存判断。`evals/package.json` 进一步提供带 `src/` 布局、Decimal 金额计算以及 pricing/discount/shipping/service 边界的包级场景。每个任务声明隐藏的期望改动范围，但该信息不会进入模型 prompt。

复现外部 h11 基准（下载内容和工作区均被 Git 忽略）：

```powershell
.\scripts\prepare_h11_benchmark.ps1
.\scripts\run_demo.ps1 -Suite evals\external-h11.json
```

准备脚本固定到 h11 `v0.16.0` 并校验归档 SHA-256，同时保留 clean 与 injected-bug 两份工作区。该结果属于在真实第三方源码上注入的受控回归，不是上游真实 issue 或 SWE-bench 成绩。

运行 V1.3 的五场景、三次重复 context A/B：

```powershell
.\scripts\run_demo.ps1 -Suite evals\context-matrix.json
```

manifest 通过 `case`、`repetitions`、`variant` 和 `baseline_variant` 声明配对实验，并以 `seed_failure_context` 控制上下文。30 次 DeepSeek + Docker 实测中，两组都完成 15/15 修复和 15/15 范围命中；context-on 的平均请求减少 23.81%，平均 tokens 减少 22.80%。15 个配对中 token 有 11 对更省、4 对更贵，说明上下文定位准确性会决定收益。详见 [V1.3 multi-case context matrix](docs/v1.3-context-matrix-results.md)。单场景先导实验保留在 [V1.3 context A/B](docs/v1.3-context-ab-results.md)。

长批量在进程中断后可续跑。指定原输出目录后，Runner 会校验 suite、模型、manifest 和全部 source SHA-256，复用已完成 trial，只执行缺失项：

```powershell
.\scripts\run_demo.ps1 -Suite evals\context-matrix.json `
  -Output eval-results\context-matrix-YOUR_TIMESTAMP -Resume
```

单元测试使用 mock/scripted provider，因此不会产生 API 费用；项目主路径和 `repofix-eval` 始终使用真实 API provider。

## 安全边界与非目标

V1.2 只允许 Agent 读取仓库可见文件、写入仓库普通文件、运行 pytest，以及查看 Git diff/status。Docker backend 会隔离仓库测试代码；Harness 与 Agent 文件写入仍运行在宿主机，因此它不是完整 OS sandbox。

当前不包含 LangGraph、multi-agent、MCP、完整 Docker sandbox、SWE-bench/BugsInPy。选择标准库状态机和小模块，是为了让控制流、安全边界和失败行为可以直接审查与面试讲解。

## 文档

- [架构与数据流](docs/architecture.md)
- [演示流程](docs/demo.md)
- [面试讲解指南](docs/interview-guide.md)
- [DeepSeek 配置](docs/deepseek-setup.md)
- [V0.9 回归集设计](docs/v0.9-regression-suite.md)
- [真实 benchmark 结果](docs/v0.9-deepseek-results.md)
- [Package-style 真实验证](docs/package-scenario-results.md)
- [外部 h11 v0.16.0 隔离修复](docs/external-h11-results.md)
- [V1.3 五场景 context 配对实验](docs/v1.3-context-matrix-results.md)
