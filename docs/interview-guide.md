# 面试讲解指南

## 30 秒版本

RepoFix-Harness 是一个面向 Python 仓库 Bug 修复的 Coding Agent Harness。真实 LLM 自主查看、搜索和修改代码；Harness 负责有界上下文、阶段工具权限、预算、checkpoint、Docker 测试、回滚和独立评测。项目在 Click 真实上游 Bug 上完成独立 3/3 稳定修复，也保留了复杂 h11 状态机的波动结果；V3.7–V3.9 在冻结实验身份下比较模型和 thinking 配置，并用 h11/Tomli 的相反结果证明参数收益依任务而变，不能凭主观感觉选模型。

## 3 分钟版本

1. **问题**：LLM 会写代码，但直接让它调用 shell 不可靠——可能越权、循环、浪费 token，或者只口头宣称修复。
2. **边界**：我把目标限制为 Python repository repair，而不是复刻通用 Codex。
3. **核心循环**：Harness 构造上下文，模型返回一个 JSON action，工具执行后把 observation 写入 trace，再进入下一轮。
4. **可信验证**：运行前后 pytest 都由 Harness 独立执行；模型的 `finish` 只是请求结束，不代表成功。
5. **安全与恢复**：路径和命令有白名单，写入前保存原始字节，回滚前比较结束哈希，避免覆盖用户后续编辑。
6. **成本与稳定性**：限制 step/request/token，统计缓存和成本，对限流/超时退避重试，并阻止第三次相同动作。
   批量 suite 还会把每个 task 的请求上限乘以 repetitions；理论总量超过 manifest 明确授权时，模型调用前直接拒绝。
7. **可观测性**：每次调用都记录 context 长度、phase working set、历史裁剪、预算准入责任和自动源码选择依据，但这些诊断不进入模型 history。
8. **评测**：先用自建 deterministic suite 验证闭环，再转向 checksum-qualified 真实上游 commit。最终 9-trial gate 是 4/9 成功、4/9 精确范围，74 次请求、342,070 tokens；每个成功都通过完整上游 pytest。
9. **对照实验**：五类 Bug 各做三次 context-on/off 配对，共 30 次真实修复；两组都是 15/15 成功和范围命中，context-on 平均请求减少 23.81%、token 减少 22.80%，但间接定位场景也出现反例。

## 最值得展开的技术点

### 为什么不能相信模型的 finish？

模型可能误判测试结果，甚至没有运行完整测试。RepoFix 把状态判定权放在 Harness：收到 finish 后重新运行独立 pytest，只有通过才是 `success`。

### checkpoint/resume 难在哪里？

不只是保存聊天历史，还要保存 task、repo、run ID、步骤、usage、evaluation 和工具 observation；resume 时必须校验仓库和任务一致，并重新绑定同一个 workspace journal。

### 回滚为什么要 before hash 和 after hash？

before snapshot 用于恢复；after hash 用于判断 Agent 结束后用户是否又编辑了文件。如果当前 hash 不等于 Agent 最后写入 hash，默认拒绝恢复，避免覆盖用户工作。

### 为什么限制成 pytest，而不是任意 shell？

项目目标是可解释的 repair Harness。pytest 已足够形成执行反馈闭环，同时显著缩小命令注入风险；不可信仓库的测试进入禁网、只读挂载、无提权的受限 Docker 容器。Harness 自身仍在宿主机运行，因此不能宣称完整 OS sandbox。V3.3 还把“命令被拒绝”和“pytest 真正失败”分开，避免工具错误污染修复状态。

### 为什么不用 LangGraph？

当前只有线性单 Agent loop，自定义状态机约束清楚、依赖少、容易测试。框架应该解决真实复杂度，而不是成为简历关键词。

## 如何诚实描述结果

可以说：

> 在五类自建 deterministic Python Bug 上完成 5/5 真实模型修复，并同时验证改动文件范围。

也可以说：

> 在三个真实上游 Bug 的九次冻结评测中完成 4/9 verified repairs；简单边界问题 3/3，复杂 parser 问题 0/3，因此项目证明的是 Harness 的可信闭环，而不是模型已经达到生产级修复率。

最新结果还可以补充：关闭 DeepSeek 默认 high thinking 后，两个原本困难的真实案例在六次重复门禁中完成 4/6，且 6/6 只修改预期文件；这说明 Provider 配置会显著影响 Agent 工具稳定性，但结果仍不是生产成功率。

最终同案例对照是 V2.0 的 4/9 提升到 V2.3 的 8/9，同时 token 减少 29.9%、估算成本减少 54.6%、格式重试从 31 次降到 0。需要强调这来自 Harness 与 Provider 配置共同改进，样本只有三个 Bug，不应外推成通用成功率。

为了检查是否只对调参案例有效，V2.4 又加入 h11 协议回归、跨模块订单包和 assertion-only 配置语义三类未参与近期调参的任务，各三次共 9/9。面试时要主动说明只有 h11 是第三方源码，其余两个是自建 fixture。

V2.7–V3.5 的 h11 chunk-footer 状态机是最适合讲失败分析的一组：72k 校准曾完成 1/1，V3.1 的 60k 三次门禁完成 2/3，但后续独立小样本在 0/3–1/3 波动。Harness 依次修复了 revision context、测试证据时效、拒绝命令误判、verification context 膨胀和重复预算准入；机制均有离线重放与真实 trace 证据，但最新 V3.5 仍是 0/3。正确结论是复杂修复主要受模型推理质量影响，不能靠不断放宽 Harness 预算包装成稳定成功。

V3.6 则展示“扩大覆盖面而不是继续过拟合失败例”的方法：新增 Click help rendering 上游 Bug 时先发现 Docker 无法导入标准 `src/` layout，于是统一 Local/Docker 的仓库内 `PYTHONPATH`，再冻结提交、归档哈希、测试文件和预期修改范围。单次门禁 1/1，独立三次 follow-up 3/3，所有成功均只修改 `src/click/core.py` 并通过 1,386 项完整测试。

V3.7 可用于回答“为什么默认使用 Flash 而不是更贵的 Pro”：在完全相同的 Click 三次评测中，Pro requests/tokens 明显更低，但成功率已经同为 3/3且成本高 89.68%；在 h11 难例中两者都只有 1/3，Pro 成本高 187.04%。所以当前默认 Flash 是证据驱动的性价比选择，不代表 Pro 永远更差，也不能从各三次样本外推长期胜率。

V3.8 可用于回答“thinking 是否一定更浪费”：同一 Pro/h11/60k/12-request/120s 配置下，thinking-high 从 2/3 到 3/3，并把 requests 减少 33.33%、tokens 减少 15.42%，但 reasoning output 使峰值成本仍增加 15.82%。它说明更长单次思考可能减少错误修订轮次；三对样本的 paired sign test 仍不显著，不能升级为默认路由规则。

V3.9 给出必要的反例：同一 Pro/Tomli/80k/12-request/120s 配置下，两组都是 3/3，但 thinking-high tokens 增加 39.04%、峰值成本增加 95.82%。三个配对 trial 都是 non-thinking token 更少。因此项目不把“难任务”简单等同于“开启 thinking”，也不根据一次正向实验做自动路由。

不要说：

> 达到生产级自动修复能力，或在 SWE-bench 上达到 100%。

五任务结果证明 Harness 闭环可运行，不证明对大型未知仓库的泛化能力。

V1.3 的 30 次实验进一步证明 context 机制在这组 fixture 上能降低平均资源消耗，但成功率已经饱和、每格只有三次且只使用一个模型。最诚实的结论是“定位准确时通常缩短 action path，跨文件归因不准时可能增加噪声”，不能表述为普遍提升 22.8%。

V1.4 把这个反例变成了可复现的改进实验：AST 只补充入口函数真正调用的一跳本地 helper，三组配对中请求和 tokens 都更少。不过每组仍只有三次，双侧符号检验 p=0.25；它证明机制按设计工作，不构成统计显著或跨项目泛化结论。

## 常见追问

- **如果模型一直重复 read？** 同一真实写入阶段内第三次完全相同 action 会触发 stalled。
- **如果请求中断？** 每个 event 原子保存，使用相同 task 和 repo 执行 `--resume`。
- **如果模型乱改很多文件？** 默认最多五个不同文件，suite 还比较隐藏的期望改动范围。
- **如果自动修改失败？** 可选择自动回滚，也可事后用 `repofix-runs rollback`；哈希冲突默认拒绝覆盖。
- **如何换模型？** provider 使用 OpenAI-compatible 接口，只改 BASE_URL/API_KEY/MODEL 环境变量。
- **下一步是什么？** V3.9 已得到 h11 正向、Tomli 负向的跨项目证据；下一步应增加未参与历史调参的新上游 Bug family，并积累更大的冻结矩阵后再研究可解释的难度路由。
