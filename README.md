# RepoFix-Harness

面向 Python Repository Bug Repair 的 Coding Agent Harness。输入一个代码仓库和修复任务，真实 LLM 自主选择工具完成 `inspect → pytest → read/search → patch → pytest → finish`；Harness 负责上下文、权限、预算、状态、恢复、追踪和独立评测。

项目刻意聚焦 Python 仓库修复，不做通用聊天助手、multi-agent 或“小型 Codex 全复刻”。

## 实测结果

V4.7 在同一份 4.7.0 Harness、manifest、仓库快照和 Docker 运行时上，原生完成 Flash/Pro 三案例严格对照。两组均为 3/3 verified、3/3 精确范围、0 retries；Pro 从 11 requests / 21,295 tokens 降至 8 requests / 13,074 tokens（-27.27% / -38.61%），但峰值保守成本从 `$0.00847512` 升至 `$0.01649349`（+94.61%）。新报告把差异进一步归因到每个案例的具体 repair phase：Pro 在 optional-config 案例少走一次 `ready_to_patch`、`patch_needs_revision` 和 `patch_due`，而不是笼统地只报告总请求下降。三个任务都是低成本自建 fixture、每模型单次运行，因此默认仍保持 Flash，结果不外推为模型胜率。详见 [V4.7 native phase model comparison](docs/v4.7-native-phase-model-comparison.md)。

V4.6 首次用真实 DeepSeek Flash/non-thinking 原生生成 schema-v3 报告，而不是离线回填：三个低成本 Docker 案例得到 3/3 verified、3/3 精确范围，使用 12/24 授权 requests、22,205 tokens、0 retries，估算 `$0.00633385`。报告自动汇总 12 snapshots，并按 case 分为 toy 3、optional config 4、username normalization 5；三层 telemetry 重算校验通过。详见 [V4.6 native schema-v3 gate](docs/v4.6-native-phase-telemetry.md)。

V4.5 将两份严格 identity-compatible 报告的 phase telemetry 自动做差，输出 overall 与 per-case snapshot/phase/transition delta；历史 v1/v2 报告仍可比较，但没有阶段数据时不伪造结论。对 V3.7 冻结 Click Flash/Pro 报告做确定性离线迁移后，Pro 少 6 个决策 snapshots，差异完全来自少 3 个 `ready_to_patch` 和少 3 个 `patch_attempt_failed`，与当时 requests 从 16 降到 10 一致，说明优势来自避免被拒补丁及恢复轮次。详见 [V4.5 phase-delta comparison](docs/v4.5-phase-delta-comparison.md)。

V4.4 在 V4.3 overall telemetry 上增加按 `case` 和 `variant` 分组的完整阶段统计，report schema v3 会分别从 task 明细重算三层数据并拒绝不一致结果。V4.2 冻结轨迹离线回算显示：Click 14 snapshots、`last()` 15、`numeric_range` 14，三组均为 0 次 target-read grace；其中 `last()` 有 4 个 `patch_attempt_failed` snapshots，而 numeric_range 为 0，使“请求花在哪里”能够定位到具体案例与阶段。详见 [V4.4 grouped phase telemetry](docs/v4.4-grouped-phase-telemetry.md)。

V4.3 把 `context_snapshots` 中的修复阶段提升为可校验的 report-level telemetry：自动汇总阶段次数、真实阶段切换和 `target_read_due` 激活次数，并在发布 Markdown 前从 task 明细重新计算，手工篡改汇总会被拒绝。用冻结的 V4.2 九条真实轨迹离线回算得到 43 snapshots、0 次 target-read grace 激活；阶段明细现在无需逐条解析 JSON。evaluation report schema 升级到 v2，同时继续兼容读取和恢复 v1 报告。详见 [V4.3 phase telemetry](docs/v4.3-phase-telemetry.md)。

V4.2 对 V4.1 做跨项目回归：复用 `more-itertools.last()`、`numeric_range.__reversed__()` 和 Click help rendering 三个 checksum-qualified 真实上游合同，各运行三次。默认 Flash/non-thinking 得到 9/9 verified、9/9 精确范围，43 requests / 103,631 tokens、0 retries，峰值保守成本 $0.03658515。九条轨迹都在 1–3 次导航内进入补丁，没有触发 `target_read_due`，说明新宽限只处理“第五次搜索刚发现未读目标”的边界，没有给历史稳定案例增加步骤。详见 [V4.2 cross-project regression](docs/v4.2-target-read-regression.md)。

V4.1 修复 V4.0 三条 Pro 失败轨迹共同暴露的阶段策略缺陷：第 5 次导航刚搜索到尚未读取的源码行时，不再立即强制补丁，而进入一次性的 `target_read_due`，只允许 `read/apply_patch`；完成窄读后立刻回到 patch-only。离线重放把三条旧轨迹的 placeholder 补丁前移除；同一 ItsDangerous/Pro/non-thinking/40k/12-request 三次真实门禁从 0/3 提升到 3/3，requests 从 36 降到 24（-33.33%）、tokens 从 107,158 降到 76,799（-28.33%），0 format retries，完整 100 项测试和 3/3 范围均通过。详见 [V4.1 target-read grace](docs/v4.1-target-read-grace.md)。

V4.0 新增第八个 checksum-qualified 真实上游 Bug family：ItsDangerous 必须拒绝可能出现在 URL-safe Base64 签名中的危险分隔符，同时统一处理 `str`/`bytes`。32k Flash 校准为 0/1；冻结 40k 单次对照中 Flash 0/1、Pro 1/1，Pro 用 7 requests / 21,672 tokens 完成并通过完整 100 项测试。但独立 Pro 三次 follow-up 为 0/3、3/3 精确范围，全部在 12-request 边界停止。因此该案例只证明 Pro 曾在同预算下完成，不能证明稳定胜过 Flash，也不触发自动模型路由。详见 [V4.0 ItsDangerous upstream gate](docs/v4.0-upstream-itsdangerous-separator.md)。

V3.9 在另一个真实上游困难案例 Tomli dotted-key parser 上复验 Pro thinking-high。两组均为 3/3 verified、3/3 精确范围；thinking-high requests 从 20 增至 21（+5.00%）、tokens 从 63,551 增至 88,362（+39.04%），峰值保守成本从 $0.06942469 增至 $0.13594470（+95.82%）。三个配对 trial 的 thinking tokens 全部更多，说明 V3.8 在 h11 上的收益不能直接推广；默认仍保持 Flash/non-thinking。详见 [V3.9 Tomli thinking comparison](docs/v3.9-tomli-thinking-comparison.md)。

V3.8 将 Provider request timeout 纳入实验身份，并让 `repofix-compare` 显式支持 `model` 与 `thinking_mode` 两种单变量对照。冻结 Pro h11 三次组中，non-thinking 为 2/3 verified，thinking-high 为 3/3；thinking-high requests 从 33 降到 22（-33.33%）、tokens 从 162,442 降到 137,393（-15.42%），峰值保守成本从 $0.18748136 增至 $0.21714925（+15.82%）。每组只有三次且同案例历史波动明显，因此这是 thinking-high 的正向小样本证据，不是稳定胜率结论。详见 [V3.8 Pro thinking-high comparison](docs/v3.8-thinking-high-comparison.md)。

V3.7 在冻结的 V3.6.0 Harness 上完成 `deepseek-v4-flash` 与 `deepseek-v4-pro` 的跨模型对照，并新增 `repofix-compare` 严格比较入口。Click 三次组均为 3/3 verified；Pro 将 requests 从 16 降到 10（-37.5%）、tokens 从 46,554 降到 25,323（-45.61%），但峰值保守成本增加 89.68%。h11 难例两组均为 1/3 verified、3/3 范围命中；Pro requests 增加 6.25%、tokens 仅减少 1.5%，成本增加 187.04%。因此当前 non-thinking 配置没有证据支持把默认模型从 Flash 切到 Pro。详见 [V3.7 frozen cross-model comparison](docs/v3.7-model-comparison.md)。

V3.6 扩展到第七个 checksum-qualified 真实上游 Bug family：Click 在渲染 option help 时，会把任意默认对象与空字符串直接比较，遇到拒绝字符串比较的 `__eq__` 会抛异常。为支持该标准 `src/` 布局仓库，本地与 Docker pytest 后端现在都使用只指向目标仓库根目录及 `src/` 的隔离 `PYTHONPATH`。冻结门禁为 1/1 verified、1/1 精确范围，使用 6 requests / 17,468 tokens；独立三次 follow-up 为 3/3 verified、3/3 精确范围，使用 15 requests / 41,427 tokens、0 retries。每次最终验收均为 1,386 passed、21 skipped、1 xfailed。详见 [V3.6 Click upstream gate](docs/v3.6-upstream-click-help.md)。

V3.5 消除 compact working set 上的重复保守准入：支持 next-action token allowance 的 provider 根据完整 prompt 和最低输出空间做最终判断，普通 context 仍用历史保守估算，硬 run 上限不增加。同 V3.4 auto-verify follow-up 可比的 h11 三次门禁为 0/3 verified、3/3 范围命中，使用 33 requests / 176,119 tokens / 5 format retries，估算 $0.06803926；两条由 Provider 在 60k 内拒绝，一条在 12/12 停止并已获得第三次补丁机会。机制移除了提前拦截，但没有改善该状态机案例的模型修复结果。详见 [V3.5 provider-managed residual admission](docs/v3.5-provider-managed-admission.md)。

V3.4 将 working set 扩展到 `patch_needs_verification`：只向模型保留当前补丁及其后的工具事件，旧导航仍留在完整 trace。离线重放 V3.3 的 5 个验证请求时，context 从 22–24k 降到 2.5–10.2k；真实门禁也降到 3.3–11.2k，但结果为 0/3 verified、3/3 范围命中，使用 35 requests / 164,905 tokens / 2 format retries，估算 $0.06341088。三次都写出第二补丁但仍未通过，瓶颈已转为有限请求内的补丁质量与显式验证开销。详见 [V3.4 verification working set](docs/v3.4-verification-working-set.md)。

V3.4 另做了不并入主结果的 auto-verify follow-up：仅启用已有 `verify_after_patch`，同案例三次仍为 0/3，但请求从主门禁 35 降到 28，tokens 为 162,838，4 format retries，估算 $0.06690598。三条均在 token reserve 停止，其中一条剩余 6,611、准入估算 6,758，只差 147 tokens；这支持下一步收紧 working-set 请求的保守准入缓冲，而不是增加硬预算。

V3.3 针对 V3.2 两条轨迹中的 evidence provenance 缺陷：只有带实际返回码或超时标记的 `run_command` 才算 pytest 证据；被权限层拒绝的命令仍写入 trace，但不改变测试状态。冻结 h11 三次门禁为 1/3 verified、3/3 范围命中，使用 30 requests / 161,327 tokens / 1 format retry，估算 $0.06474308；成功项通过完整 78 项验收。另两项都在第二补丁的真实 pytest 仍失败后触及 token reserve，并暴露验证请求重新膨胀到 22–24k context 的成本问题。详见 [V3.3 test evidence provenance](docs/v3.3-test-evidence-provenance.md)。

V3.2 修复 V3.1 唯一失败轨迹暴露的 verification freshness 问题：每次新补丁真正改动文件后，旧 pytest 结论立即失效；若同一补丁携带自动测试结果，再以该结果更新状态。冻结的同配置 h11 三次门禁为 0/3 verified、3/3 范围命中，使用 34 requests / 174,480 tokens / 3 format retries，估算 $0.06662267。前两次第二补丁后确实回到验证阶段，但只有一次真正执行 pytest；另一次非法 `sed` 与第三次非法 `python` 被工具正确拒绝，却被 Context 错误算作失败测试证据。V3.2 证明状态时序修复生效，但真实结果退化，不能宣称能力提升。详见 [V3.2 verification freshness](docs/v3.2-verification-freshness.md)。

V3.1 将补丁失败后的模型 context 收敛为 revision working set：最近有效补丁、最新失败 pytest、以及失败后的窄读/搜索；首次补丁前不裁剪，完整 trace 不删除。重放 V3.0 三条真实失败轨迹时，下一修订请求分别减少 12,523、13,376、12,933 字符。随后同一 h11、同一 non-thinking 60k 配置的冻结三次门禁达到 2/3 verified、3/3 范围命中，使用 28 requests / 155,828 tokens / 1 format retry，估算 $0.06458051；两次成功均通过完整 78 项 h11 验收。剩余失败暴露出新补丁后仍沿用旧 pytest 失败状态的问题，因此这是一轮明确改善，不是稳定性结论。详见 [V3.1 revision working set](docs/v3.1-revision-working-set.md)。

V3.0 针对 V2.9 暴露的 residual-budget recovery：格式重试会在保守估算重复输入后，将剩余硬 token 预算动态分配给输出，最低 256，run 上限不放松。机制单测通过，真实冻结 60k 门禁中也确实发出了一次缩减后的额外 retry；但结果仍为 0/3 verified、3/3 范围命中、27 requests / 170,459 tokens / 4 retries，估算 $0.06453922。两条轨迹在普通下一请求前预算不足，另一条 retry 后仍返回无效补丁。V3.0 证明 residual recovery 可执行，没有证明修复能力提升。详见 [V3.0 residual-budget format recovery](docs/v3.0-residual-format-recovery.md)。

V2.9 针对 V2.8 六条 h11 轨迹共有的修订瓶颈加入 evidence-aware revision cap：pytest 已直接指向刚修改源码时，只允许一次窄读便强制再次补丁；仅指向测试断言时仍保留两次导航。离线重放准确改变三条失败轨迹，但后续冻结 60k 门禁仍为 0/3 verified、3/3 范围命中、27 requests / 156,017 tokens / 3 format retries，估算 $0.06299875。它比 V2.8 同预算少约 5.7% tokens，却暴露出补丁格式纠错所需的完整 4,096 output reserve 无法装入剩余预算；这是负结果，不宣称成功率改善。详见 [V2.9 actionable revision cap](docs/v2.9-actionable-revision-cap.md)。

V2.8 针对 V2.7 的长轨迹优化 Harness context：新 pytest 证据替代旧 baseline 正文，重复 read/search 只保留最新上下文副本，失败行实际使用的本地 import 优先。离线重放第 8–11 步减少 11,531 个上下文字符。后续冻结 DeepSeek 门禁仍揭示明确边界：non-thinking 60k 为 0/3 verified、3/3 范围命中、27 requests / 165,403 tokens；独立 72k follow-up 为 1/3 verified、3/3 范围命中、33 requests / 190,062 tokens，唯一成功通过完整 78 项 h11 测试。两组不合并，V2.8 没有证明该状态机修复已稳定。详见 [V2.8 context compaction and model gates](docs/v2.8-context-compaction.md)。

V2.7 新增第六个 checksum-qualified 真实上游修复，也是首个协议解析状态机案例：h11 的 `ChunkedReader` 会无条件丢弃 chunk body 后两个字节，却不验证它们是否为必须的 CRLF。四次预先区分的预算校准依次为 auto 42k：0/1、non-thinking 42k：0/1、non-thinking 60k：0/1、non-thinking 72k：1/1；最后一次在 12/12 请求边界完成，独立完整验收为 78 passed。该结果说明复杂增量状态修复对轨迹和预算敏感，只能作为能力边界与预算校准，不能宣称稳定成功。详见 [V2.7 upstream h11 chunk footer calibration](docs/v2.7-upstream-h11-chunk-footer.md)。

V2.6 新增第五个 checksum-qualified 真实上游修复：`numeric_range.__reversed__()` 在空 range 上错误抛出 `IndexError`。指定门禁 1/1 verified，用 5 requests / 16,163 tokens 完成；随后独立重复三次得到 3/3 verified、3/3 精确范围、14 requests / 44,353 tokens。两组实验各有 1 次已恢复的 format retry，完整验收均为 716 passed、19,896 subtests passed；指定门禁与稳定性 follow-up 分开报告。详见 [V2.6 upstream numeric range gate](docs/v2.6-upstream-numeric-range.md)。

V2.5 新增第四个 checksum-qualified 真实上游修复：`more-itertools.last()` 在 `__reversed__ = None` 时错误进入 `reversed()` 路径。DeepSeek 在一次冻结门禁中用 6 requests / 23,337 tokens 完成修复，0 format retries，只修改预期源码文件；独立完整验收为 679 passed、1 skipped、12,078 subtests passed。随后独立重复三次，得到 3/3 verified、3/3 精确范围、14 requests / 46,080 tokens 和 1 次已恢复的 format retry。单次门禁与重复 follow-up 分开报告，不合并选择结果。详见 [V2.5 upstream `last()` gate](docs/v2.5-upstream-last.md)。

V2.4 将冻结策略移到未参与近期调参的三个 Bug family：h11 第三方源码注入回归、`src/` 跨模块订单 fixture、assertion-only 配置 fixture，各运行三次。结果为 9/9 verified、9/9 精确范围、31 requests / 72,547 tokens、0 format retries，估算成本 $0.02419832。只有 h11 使用第三方真实源码，其余为自建场景，因此该结果是泛化 smoke gate，不是 9 个真实 upstream issue。详见 [V2.4 generalization gate](docs/v2.4-generalization.md)。

V2.3 在与 V2.0 相同的三个上游 Bug、九次交错 trial 上完成可比复验：verified repairs 从 4/9 提升到 8/9，requests 从 74 降至 66，tokens 从 342,070 降至 239,833，format retries 从 31 降至 0，估算成本下降 54.6%。唯一失败揭示空搜索被误当作证据的问题；独立 search-evidence follow-up 修复后 Tomli 1/1 完成。主结果与 follow-up 不合并。详见 [V2.3 comparable stability](docs/v2.3-comparable-stability.md)。

V2.2 在冻结的 DeepSeek non-thinking 配置上对两个困难上游 Bug 各重复三次，主稳定性门禁完成 4/6 verified repairs、6/6 改动范围命中，53 requests / 231,784 tokens，且没有格式重试。随后针对两条预算失败轨迹加入 patch 后最多两次导航的 revision cap，独立 follow-up 为 2/2。主门禁与 follow-up 分开报告，不合并选择结果。详见 [V2.2 non-thinking stability](docs/v2.2-nonthinking-stability.md)。

V2.1 针对 V2.0 暴露的 DeepSeek 空响应与补丁截断问题增加原生工具原地纠错、阶段输出上限和显式 thinking 配置。在两个困难上游案例的顺序式 before/after gate 中，API 默认 thinking 为 0/2，显式 `thinking=disabled` 为 2/2；后者完整测试和改动范围均通过，token 从 108,138 降至 73,192，估算成本从 $0.06776712 降至 $0.03117027。每案例仅运行一次，不能当作稳定成功率。详见 [V2.1 Provider recovery](docs/v2.1-provider-recovery.md)。

V2.0 使用 `deepseek-v4-flash` 对三个 checksum-qualified 真实上游 Bug 各运行三次，共 9 个交错 trial：

| 案例 | 完整修复 | 范围命中 |
|---|---:|---:|
| more-itertools `sliced()` 负数边界 | 3/3 | 3/3 |
| more-itertools running min/max 稳定性 | 1/3 | 1/3 |
| Tomli dotted-key parts 上限 | 0/3 | 0/3 |
| **总计** | **4/9（44.4%）** | **4/9** |

整套实际使用 74/108 授权请求、342,070 tokens，估算成本 $0.19253849。所有成功任务均通过独立完整上游 pytest，并只修改预期实现文件；失败由 3 次 invalid model output 和 2 次 token reserve 构成。这是当前真实稳定性边界，不等同于 SWE-bench 或生产成功率。详见 [V2.0 stability gate](docs/v2.0-stability-results.md)。

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
- 首轮 context 自动附带 pytest traceback 引用的仓库源码片段；若只命中测试文件，会优先解析失败行实际使用的本地 import，再定位入口函数并补充该函数实际调用的一跳本地实现，同时过滤外部路径与控制目录
- 有界 context、工具输出头尾压缩、最近进度摘要；新 pytest 证据会替代重复的初始 baseline 正文，重复 read/search 在模型上下文只保留最新证据
- 失败补丁进入 revision phase 后，模型只看到最近补丁、最新失败测试和失败后的导航 working set；首次补丁前与落盘 trace 不裁剪
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
- 报告比较会先校验 manifest、source、Harness、Docker、timeout、预算与任务身份；显式选择 `model` 或 `thinking_mode` 单变量后，再计算整体和逐 trial 的成功率、requests、tokens 与成本差异
- 配对实验按 case + trial 比较成功结果与资源差值，并记录 manifest/fixture SHA-256
- 配对资源指标附带 better/tied/worse 计数和不依赖第三方统计库的双侧精确符号检验
- 每个 trial 后原子更新 `progress.json`；单次 runner 异常被隔离，后续任务继续执行
- 完成时同时生成机器可读 `report.json` 和可直接审阅的 `report.md`
- 发布报告前重算聚合完整性；每次实际复制后重验 source 指纹，禁止中途混入变化的 fixture
- 报告持久化声明模型、实际模型计数、输出上限和成本单价；续跑时必须完全一致
- Harness 包版本和源码树 SHA-256 也属于实验身份，防止不同实现版本静默续跑
- Docker trial 保存完整 preflight checks，并汇总 daemon 版本、镜像 SHA-256 与容器 pytest 指纹
- 受限 Docker pytest 后端：禁网、只读仓库、无提权并限制 CPU、内存和进程数
- 本地与 Docker pytest 均支持根目录包和标准 `src/` 布局；导入路径只绑定当前目标仓库，不继承宿主机 `PYTHONPATH`

架构与模块职责见 [Architecture](docs/architecture.md)。

## 快速开始

```powershell
cd <project-path>\RepoFix-Harness
.\scripts\setup_project.ps1
.\.venv\Scripts\Activate.ps1
```

同时构建 Docker pytest 镜像：

```powershell
.\scripts\setup_project.ps1 -BuildSandbox
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

格式纠错默认保留正常输出上限；接近 run token 边界时，会在估算重复输入后缩小该次 retry 的输出上限，最低 256 tokens。若最低额度也无法安全容纳，Harness 仍在请求前停止并执行独立最终验收。

Action Registry 对参数类型、行号范围和两种 patch 模式提供同一份结构化定义；Context 根据已完成的定位、修改和测试状态标记 repair phase，在证据足够时优先推动最小局部补丁，验证通过后推动结束，而不是继续重复读取。

Harness 还会把 repair phase 变成实际工具策略：例如 `patch_due` 请求只向模型暴露 `apply_patch`，`verified_patch` 只暴露 diff/status/finish。该限制同时作用于原生 Function Calling 和 JSON fallback，阶段外动作会被 Provider 拒绝。

补丁后的 pytest 若直接指向已修改源码，revision phase 只允许一次窄导航就进入 `patch_due`；仅有测试断言时仍允许两次，避免盲目强制修改。

单仓库 CLI 默认显示实时 repair phase、剩余预算、动作、补丁后定向测试及最终 before/after 摘要；`--quiet` 隐藏实时步骤但保留摘要，`--json` 只输出最终 RunState JSON。Preflight 判定目标不是 Git worktree 时，Provider 不再看到不可用的 git 工具。

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

## 五个命令行入口

```text
repofix       运行单个真实 Agent 修复任务
repofix-eval  在隔离副本中顺序执行 JSON evaluation suite
repofix-runs  列出、查看或安全回滚历史 run
repofix-doctor 在不调用模型的情况下检查仓库运行条件
repofix-compare 严格比较两个身份兼容的 evaluation report
```

常用操作：

```powershell
repofix-eval --suite evals/regression.json
.\scripts\run_demo.ps1 -Suite evals\package.json
repofix-runs --repo <repo> list
repofix-runs --repo <repo> show latest
repofix-runs --repo <repo> rollback latest
repofix-compare --baseline <flash-report.json> --candidate <pro-report.json> --output <comparison-dir>
repofix-compare --dimension thinking_mode --baseline <off.json> --candidate <on.json> --output <comparison-dir>
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

准备并运行 V3.6 Click help rendering 真实上游案例：

```powershell
.\scripts\prepare_upstream_click_help_v3.6.ps1
.\scripts\run_demo.ps1 -Suite evals\upstream-click-help-v3.6.json

.\scripts\prepare_upstream_itsdangerous_separator_v4.0.ps1
.\scripts\run_demo.ps1 -Suite evals\upstream-itsdangerous-separator-v4.0.json
```

准备脚本固定 Click PR #3299 的第一父提交与 merge commit，校验两份归档 SHA-256，只把上游回归测试复制到 buggy snapshot，并保护 `src/click/core.py` 仍等于父提交。冻结单次门禁与后续三次稳定性结果分开报告，不合并成功率。

V4.0 的 ItsDangerous 脚本同样固定父/修复 commit 和归档哈希，只导入上游 `tests.py`，并保护父版本 `itsdangerous.py`。其 Flash/Pro 单次对照与 Pro 三次 follow-up 也分别报告，避免用一次成功覆盖后续 0/3。

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
- [V1.7 Patch readiness 定向实验](docs/v1.7-patch-readiness.md)
- [V1.8 阶段工具策略真实门禁](docs/v1.8-phase-policy-results.md)
- [V1.9 CLI 真实演示](docs/v1.9-cli-demo.md)
- [V2.0 三案例九次稳定性门禁](docs/v2.0-stability-results.md)
- [V2.1 Provider 恢复与 thinking 对照](docs/v2.1-provider-recovery.md)
- [V2.2 non-thinking 重复稳定性与 revision cap](docs/v2.2-nonthinking-stability.md)
- [V2.3 与 V2.0 同案例可比稳定性复验](docs/v2.3-comparable-stability.md)
- [V2.4 新 Bug family 泛化门禁](docs/v2.4-generalization.md)
- [V2.5 第四个 checksum-qualified 真实上游修复](docs/v2.5-upstream-last.md)
- [V2.6 第五个 checksum-qualified 真实上游修复](docs/v2.6-upstream-numeric-range.md)
- [V3.1 Revision working set 与真实门禁](docs/v3.1-revision-working-set.md)
- [V3.2 当前补丁的测试证据时效](docs/v3.2-verification-freshness.md)
- [V3.3 pytest 证据来源判定](docs/v3.3-test-evidence-provenance.md)
- [V3.4 当前补丁的验证工作集](docs/v3.4-verification-working-set.md)
- [V3.5 Provider 管理的剩余预算准入](docs/v3.5-provider-managed-admission.md)
- [V3.6 Click `src/` 布局真实上游门禁](docs/v3.6-upstream-click-help.md)
- [V3.7 Flash/Pro 冻结跨模型对照](docs/v3.7-model-comparison.md)
- [V3.8 Pro thinking-high 冻结对照](docs/v3.8-thinking-high-comparison.md)
- [V3.9 Tomli thinking-high 跨项目复验](docs/v3.9-tomli-thinking-comparison.md)
- [V4.0 ItsDangerous 危险分隔符真实上游门禁](docs/v4.0-upstream-itsdangerous-separator.md)
- [V4.1 search-hit target-read 阶段修复](docs/v4.1-target-read-grace.md)
- [V4.2 target-read 跨项目回归门禁](docs/v4.2-target-read-regression.md)
- [V4.3 报告级 repair-phase telemetry](docs/v4.3-phase-telemetry.md)
- [V4.4 按案例与 variant 分组的 phase telemetry](docs/v4.4-grouped-phase-telemetry.md)
- [V4.5 严格比较中的 phase delta](docs/v4.5-phase-delta-comparison.md)
- [V4.6 真实模型原生 schema-v3 门禁](docs/v4.6-native-phase-telemetry.md)
- [V4.7 原生 Flash/Pro 阶段归因对照](docs/v4.7-native-phase-model-comparison.md)
