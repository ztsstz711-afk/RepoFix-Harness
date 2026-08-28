# 面试讲解指南

## 30 秒版本

RepoFix-Harness 是一个面向 Python 仓库 Bug 修复的 Coding Agent Harness。真实 LLM 自主查看、搜索和修改代码；Harness 负责有界上下文、阶段工具权限、预算、checkpoint、Docker 测试、回滚和独立评测。最终使用 DeepSeek 对三个真实上游 Bug 各运行三次，完成 4/9 个完整套件修复；简单边界案例 3/3，复杂 parser 案例 0/3，结果如实展示了 Harness 已完整、模型稳定性仍有限。

## 3 分钟版本

1. **问题**：LLM 会写代码，但直接让它调用 shell 不可靠——可能越权、循环、浪费 token，或者只口头宣称修复。
2. **边界**：我把目标限制为 Python repository repair，而不是复刻通用 Codex。
3. **核心循环**：Harness 构造上下文，模型返回一个 JSON action，工具执行后把 observation 写入 trace，再进入下一轮。
4. **可信验证**：运行前后 pytest 都由 Harness 独立执行；模型的 `finish` 只是请求结束，不代表成功。
5. **安全与恢复**：路径和命令有白名单，写入前保存原始字节，回滚前比较结束哈希，避免覆盖用户后续编辑。
6. **成本与稳定性**：限制 step/request/token，统计缓存和成本，对限流/超时退避重试，并阻止第三次相同动作。
   批量 suite 还会把每个 task 的请求上限乘以 repetitions；理论总量超过 manifest 明确授权时，模型调用前直接拒绝。
7. **可观测性**：每次调用都记录 context 长度、历史裁剪和自动源码选择依据，但这些诊断不进入模型 history。
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

V1.4 的目标是可解释的 repair Harness。pytest 已足够形成执行反馈闭环，同时显著缩小命令注入风险；不可信仓库的测试进入禁网、只读挂载、无提权的受限 Docker 容器。Harness 自身仍在宿主机运行，因此不能宣称完整 OS sandbox。

### 为什么不用 LangGraph？

当前只有线性单 Agent loop，自定义状态机约束清楚、依赖少、容易测试。框架应该解决真实复杂度，而不是成为简历关键词。

## 如何诚实描述结果

可以说：

> 在五类自建 deterministic Python Bug 上完成 5/5 真实模型修复，并同时验证改动文件范围。

也可以说：

> 在三个真实上游 Bug 的九次冻结评测中完成 4/9 verified repairs；简单边界问题 3/3，复杂 parser 问题 0/3，因此项目证明的是 Harness 的可信闭环，而不是模型已经达到生产级修复率。

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
- **下一步是什么？** 更换或对照更稳定的 coding model，并针对长 reasoning 导致的空响应/截断 action 做 Provider 层实验；不是先堆 multi-agent。
