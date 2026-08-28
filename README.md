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

V1.3 把单场景验证扩展为五类 Bug、context-on/off 各三次的 30-trial 配对矩阵。两组均完成 15/15 修复与 15/15 范围命中；context-on 平均请求减少 23.81%、平均 tokens 减少 22.80%，但跨文件间接定位也出现 token 增加反例。V1.3 同时加入 trial 失败隔离、断点续跑、逐对统计、suite 请求授权、manifest/source/model/Docker 指纹、聚合完整性校验以及自动 Markdown 报告。V1.4 针对这个反例增加了受限的调用感知扩展：当测试导入的入口函数继续调用本地 helper 时，只补充该函数体内真正调用到的一跳实现，不递归遍历整个依赖图。

V1.4 使用同一反例完成三组交错 DeepSeek + Docker A/B：两组均 3/3 修复成功且 3/3 只改预期文件；context-on 三次都在首个 action 直接修改真正的 helper，平均请求从 6 降至 3（-50%），平均 tokens 从 8,360 降至 3,946（-52.8%）。这是针对单一 fixture、每组三次的机制验证，不是普遍性能结论。

## 核心能力

- 自主 Agent Loop：模型每轮选择一个结构化 action
- 工具运行时：`list/search/read/apply_patch/run_command/git_diff/git_status`
- `apply_patch` 优先执行唯一匹配的局部替换，避免小改动重传整个文件；创建文件时仍支持完整内容
- 真实 OpenAI-compatible provider，可切换 DeepSeek、Gemini 等服务
- 独立 baseline/final pytest，不接受模型口头宣称“已修复”
- baseline 的命令与压缩后失败输出直接进入首轮 context，模型无需先重复运行完整测试
- 首轮 context 自动附带 pytest traceback 引用的仓库源码片段；若只命中测试文件，会通过本地 import 定位入口函数，并补充该函数实际调用的一跳本地实现，同时过滤外部路径与控制目录
- 有界 context、工具输出头尾压缩、最近进度摘要
- 每步持久化 context 选择元数据，记录自动选中文件、原因、行号与字符预算，但不重复保存源码正文
- step/request/token 预算、成本估算、限流与超时重试
- suite 可声明总请求授权值；理论最坏请求量在运行前按 repetitions 展开校验
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
- 报告持久化声明模型、实际模型计数、输出上限和成本单价；续跑时必须完全一致
- Harness 包版本和源码树 SHA-256 也属于实验身份，防止不同实现版本静默续跑
- Docker trial 保存完整 preflight checks，并汇总 daemon 版本、镜像 SHA-256 与容器 pytest 指纹
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

为采用特定测试入口的仓库指定快速反馈测试；最终仍用完整套件验收：

```powershell
repofix --repo <python-repo> --task "Fix the parser bug" `
  --test-command "pytest -q tests/parser/test_regression.py" `
  --final-test-command "pytest -q tests"
```

两项命令都只接受 pytest 调用。`--test-command` 用于快速 baseline 和模型迭代反馈；`--final-test-command` 专用于成功判定、预算边界验证和回滚后验证。未提供最终命令时会自动沿用前者，兼容原有行为。环境变量分别为 `REPOFIX_TEST_COMMAND`、`REPOFIX_FINAL_TEST_COMMAND`，evaluation task 使用同名 JSON 字段。

对快速定向测试，可启用 `--verify-after-patch`（或 `REPOFIX_VERIFY_AFTER_PATCH=1`）。Harness 会在每次实际文件修改后自动执行 `--test-command`，把通过/失败结果附在补丁观察中；该结果只用于迭代反馈，最终成功仍必须通过 `--final-test-command`。

使用受限 Docker 容器执行所有 pytest：

```powershell
.\scripts\build_sandbox.ps1
repofix --repo <python-repo> --task "Fix the failing tests" --execution-backend docker
```

Docker backend 默认禁用网络、只读挂载仓库、丢弃 capabilities、禁止提权，并限制 CPU、内存和进程数。模型仍在 Harness 中决策，只有测试代码进入容器执行。

Local backend 仅用于可信仓库；它会移除 `REPOFIX_*` 以及常见 key/token/password/credential 环境变量，但无法提供文件系统隔离。外部仓库应使用 Docker backend。单次模型响应默认限制为 2,048 output tokens，可通过 `REPOFIX_MAX_OUTPUT_TOKENS` 调整。

Provider 默认请求 OpenAI-compatible JSON mode，减少动作格式错误；若服务返回已知的空 JSON content，同一动作的下一次重试会自动降级为普通文本模式。若某个旧兼容端点完全不支持 `response_format: json_object`，可设置 `REPOFIX_JSON_MODE=0` 退回纯 prompt 约束。

Provider 还会优先使用 OpenAI-compatible Function Calling，把注册工具转成 JSON Schema 并要求单次只调用一个工具；若响应没有合法 tool call，会在同一动作的下一次重试自动降级到 JSON mode。旧端点可设置 `REPOFIX_NATIVE_TOOL_CALLS=0` 直接关闭。

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

最终 V1.3 代码又执行一次六 trial release gate：6/6 修复和范围命中，实际使用 26/36 授权请求、40,977 tokens，聚合完整性校验通过，并生成带模型与 Docker 镜像 SHA-256 的 JSON/Markdown 报告。

运行 V1.4 调用感知 context 的定向 A/B：

```powershell
.\scripts\run_demo.ps1 -Suite evals\call-context-ab.json
```

该 manifest 只复测 V1.3 矩阵中的跨文件反例，6/6 修复和范围命中，实际使用 27/48 授权请求、36,918 tokens，保守估算成本 $0.01350462。详见 [V1.4 call-aware context A/B](docs/v1.4-call-context-results.md)。

V1.5 开始验证真实上游 Bug，而不是继续人工注入错误。准备脚本固定三个上游修复提交，以其父提交作为 buggy implementation，只复制修复提交中的回归测试，并校验下载归档与复制结果：

```powershell
.\scripts\prepare_upstream_bugs.ps1
.\scripts\run_demo.ps1 -Suite evals\upstream-bugs-v1.5.json
```

三个案例来自 more-itertools 与 Tomli，覆盖参数边界、滑动窗口稳定性和解析器资源限制。评测最多授权 36 次请求：baseline 使用上游定向回归测试，所有最终成功判定仍运行上游完整测试集。案例设计与 commit 来源见 [V1.5 upstream bug suite](docs/v1.5-upstream-bug-suite.md)。

V1.5 指定发布闸门使用 `deepseek-v4-flash` 完成 2/3：两个 more-itertools 修复均通过完整上游套件并准确命中预期文件；Tomli 在 11 次请求内未产生补丁。整套实际使用 27/36 次授权请求、115,977 tokens，保守估算成本 $0.04467383。该结果按原样发布，不用探索性重跑拼接成功率。

V1.6 针对 Tomli 暴露的长仓库导航问题加入紧凑导航记忆、最多三跳的本地 facade 追踪、补丁后的 Harness 自动定向验证，以及 DeepSeek/OpenAI-compatible 原生 Function Calling。真实原生工具冒烟用 1 次请求返回合法 `list` 动作；固定 Tomli 门禁仍在第 7 步因 Provider 格式重试耗尽 12 次请求，未产生补丁。这个失败结果保留为当前能力边界，不通过扩大预算或挑选重跑改写结论。详见 [V1.6 navigation and native tools](docs/v1.6-navigation-and-native-tools.md)。

`context-matrix.json` 的 30 个 trial 理论请求上限为 204，并在 suite 根节点用 `max_total_requests` 明确授权。增加 repetitions 或单任务上限而不同时审查总预算，会在加载 manifest 时失败，不会调用模型。

长批量在进程中断后可续跑。指定原输出目录后，Runner 会校验 suite、模型、manifest 和全部 source SHA-256，复用已完成 trial，只执行缺失项：

```powershell
.\scripts\run_demo.ps1 -Suite evals\context-matrix.json `
  -Output eval-results\context-matrix-YOUR_TIMESTAMP -Resume
```

单元测试使用 mock/scripted provider，因此不会产生 API 费用；项目主路径和 `repofix-eval` 始终使用真实 API provider。

## 安全边界与非目标

V1.4 只允许 Agent 读取仓库可见文件、写入仓库普通文件、运行 pytest，以及查看 Git diff/status。Docker backend 会隔离仓库测试代码；Harness 与 Agent 文件写入仍运行在宿主机，因此它不是完整 OS sandbox。

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
- [V1.4 调用感知 context 定向 A/B](docs/v1.4-call-context-results.md)
- [V1.5 真实上游 Bug 集](docs/v1.5-upstream-bug-suite.md)
- [V1.6 导航记忆与原生工具调用](docs/v1.6-navigation-and-native-tools.md)
