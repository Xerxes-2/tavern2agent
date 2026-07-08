# 多 Agent

多 agent 用来隔离认知、并行候选和题材审计。想让 GM 「更聪明」不构成拆分理由。

当前推荐设计来自 evented runtime：**subagent 不写 state，不拿 CodeAct，不当陪聊 NPC；它只输出候选、视角反应或审计意见，由 GM 转成领域事件。**

载体有两种，按「子代理要不要知道秘密」选：

```txt
in-process 顾问型   pi subagent 定义 + extension 注入 player-safe 投影；
                    适合审计、视角反应、无密候选
detached 导演型     engine 直接 spawn 无工具 pi 子进程，喂入完整隐藏知识；
                    适合秘密承载的后台平行线（见「密闭导演」节）
```

## 什么时候用

至少满足一项：

| 类型 | 信号 | 推荐形态 |
|---|---|---|
| 信息隔离 | NPC 秘密、阵营、凶手身份、未揭晓真相、PC 信息不对等 | perspective / secret subagent |
| 后台并行 | 多地点并行、多 NPC 自治、阵营计划、可异步生成的新闻/传闻 | parallel-line subagent |
| 题材审计 | 长跑容易 drift、NPC 变成传感器、beat 不收口、世界不动 | timeline/showrunner auditor |
| 风格分离 | 反派、队友、吟游诗人等需要和 GM 完全不同的文风/目标 | perspective subagent |

不要因为卡复杂就拆 subagent。战斗/经济复杂通常进 engine/CodeAct，不进 subagent。

## 什么时候不用

- NPC 少且无秘密。
- 只是想让 GM 更聪明。
- 一个 TS 函数能解决的规则结算。
- 状态存储、patch 兜底、schema 校验。
- 高频轻量操作。
- 可以由 event pack / tool description 解决的调用纪律问题。

## 架构

```txt
用户 → GM → 调用相关 subagent → GM 选择/改写 → domain event → reducer → 主叙事
```

GM 负责：场景、规则、状态写入、最终叙事。

subagent 负责：某个视角的台词/反应、后台事件候选、时间线审计、风险提示。它不掌握完整状态，不直接写 state。

## 项目级硬约束

生成的 subagent 必须是 project-scope，不依赖用户全局 agent：

```txt
.pi/agents/*.md                  项目级 subagent 定义
extensions/subagents/<name>.ts    动态注入/lookup/tool 限制
tools/registry.ts                GM 调用入口
.pi/settings.json                项目依赖声明
```

约束：

- `inheritProjectContext: false`：不要继承整包项目上下文。
- `inheritSkills: false`：不要加载玩家技能目录。
- 显式配置 `tools`：通常只给 lookup / readonly 工具；不给 `code_act`。
- 显式配置 `extensions`：只加载该 subagent 的 context injector；不要省略。路径从 extension 文件所在目录推导，不靠 cwd 猜。
- 输出格式稳定：候选类 subagent 用 bare JSON；审计类 subagent 用短结构化 report。
- 发布包包含 `.pi/agents/` 和 `extensions/subagents/`；不要要求玩家装 user-scope subagent。

## 推荐分层

```txt
agent prompt        稳定职责、边界、输出格式
subagent extension  动态状态切片、秘密切片、lookup、timeline context
task                本轮触发原因 / 最近事件
chat history        必要叙事脉络
```

不要每次 task 里塞完整世界。动态事实由 extension 注入，task 只说近因。

extension 注入必须带游戏内日期、时间和时区。subagent 拿不到主时钟就会自己猜，产出「凌晨发生在白天」这类错位候选。

## 典型 subagent

### perspective / secret

用于 NPC 秘密、凶手视角、阵营视角。输出台词、动作倾向、隐瞒策略，不输出最终叙事。

```json
{
  "actorId": "npc_a",
  "visibleResponse": "...",
  "privateIntent": "...",
  "suggestedEvents": []
}
```

`privateIntent` 给 GM 决策，不进入 public memory。

### parallel-line

用于后台平行线候选。它不写新闻稿，不替代事件本体；只输出可被 GM 审核的 offscreen 候选。需要读隐藏真相/阵营私有目标才能产出候选时，用密闭导演型载体（见「密闭导演」节），不要把秘密塞进 in-process 注入。

输出必须是 bare JSON：

```json
{
  "events": [
    {
      "actorOrFactionId": "guild_red",
      "locationId": "old_port",
      "action": "move contraband before dawn",
      "consequence": "guards redirected from north gate",
      "frontstageTrace": "dock workers mention an unscheduled convoy",
      "suggestedDomainEvent": "record_offscreen_event"
    }
  ]
}
```

GM 选择后，通过 `record_offscreen_event` 或 `commit_turn` 写入。新闻、传闻、门响只是 trace，不是后台事件本体。

写入侧拒绝晚于当前时钟的候选：offscreen 事件记录已经发生的事，未来计划留在候选池或 faction plan 里。

### timeline / showrunner auditor

用于长跑审计。它检查：

- 世界是否在玩家视野外运动。
- NPC 是否有自主目标，而不是只响应玩家。
- beat 是否悬挂未收口。
- hook 是否重复滥用。
- hidden/public 是否串层。
- 当前题材是否 drift。

输出建议，不写正文，不写 state。

```json
{
  "findings": [
    { "severity": "warning", "issue": "current beat has no closure pressure", "suggestedFix": "finish_current_beat after next concrete choice" }
  ],
  "candidateEvents": []
}
```

## Subagent prompt

只写角色事实和输出边界：

```md
你是 <NPC / faction / auditor>。

## 你知道
<公开信息 + 你的秘密 / 审计上下文>

## 你不知道
<其他人的秘密 / 完整世界状态 / GM 内部规则>

## 输出
只输出指定 JSON / 反应 / 审计。不要接管场景叙事，不要写 state。
```

不要写「这是 extension 注入的 system prompt」这类实现词。

## GM 调用

task 短：

```txt
最近事件：玩家当面质问你是否背叛公会。请按你的秘密和当前情绪回应。
```

GM 收到返回后，把台词/动作织入主叙事，或把候选转成领域事件。多个 NPC / parallel-line 可并行调用。

## 状态写入

subagent 不拿 `code_act`，也不直接 patch state。需要状态变化时返回结构化建议：

```json
{
  "suggestedEvent": "record_relationship_shift",
  "actorId": "npc_a",
  "targetId": "protagonist",
  "reason": "被玩家威胁后转为戒备"
}
```

GM 决定是否通过主 engine 写入。

## 上下文注入通道

subagent 需要的 state 投影，不要让它自己读 `runtime/state.json`——那是 debug 快照，可能过期、属于别的 session/分支、或被测试进程覆盖。正确通道：主 GM 进程在 `tool_call` hook 里拦截 subagent 调用（`event.input` 官方可变），从进程内 canonical store 即时计算 subagent-safe 投影（已过滤 secrets），追加进 task 参数。要点：

- 覆盖 SINGLE / PARALLEL tasks[] / CHAIN 三种形态；幂等；注入失败不阻断调用。
- agent 合同里写明上下文以追加形式到达，并定义缺块时的降级行为。
- 投影的无密性要有测试。

本节适用于 in-process 顾问型。密闭导演型在 spawn 点由 engine 组装完整 prompt（见下节），不走 hook 注入。

## 密闭导演：engine 自持薄 spawn 接缝

后台平行线导演需要**知密**才有戏：它要读未揭示的秘密和阵营私有目标，才能产出有分量的 offscreen 候选。这与「subagent 不知道秘密」的顾问型注入是另一形态——防火墙**不是**「子代理无秘密」，而是四条构造保证：进程隔离 + 零工具 + 写不了 canon + 落地前审核。实战定型做法：

```txt
run_parallel_line 工具
  → engine 组装完整导演 prompt（persona + 安全投影 + privateFacts）
  → child_process.spawn("pi", ["-p", "--no-tools", "--no-approve",
      "--no-context-files", "--model", 后台模型,
      "--session-dir", 密闭目录, "--session-id", runId, prompt])
      detached + unref，立即返回 run_id
下一轮 harvest 工具
  → engine 按 runId glob 子进程 session jsonl，取最终 assistant text
  → parse 门校验结构（return-trip gate），过了才可转成 offscreen 事件
```

构造点逐条对应不变量，替换底座时一条都不能少：

- `--no-tools`：子进程物理上调不了任何领域工具，写不了 canon。
- `--no-approve --no-context-files`：不加载项目 extension / AGENTS.md / settings，没有任何回到 canonical state 的路径。
- 独立进程 + 独立 session：秘密只进子进程工作记忆，不进主 GM context。
- reviewed-before-landing：父进程的 parse 门 + 台账是候选变成 offscreen 事件的唯一通路。
- secrets-at-rest：子进程 transcript 必然含 privateFacts，`--session-dir` 指向 gitignored 的项目隔离目录（与 `PI_CODING_AGENT_DIR` 下的敏感文件同级），不进发布包。

### 不要用 subagent 框架

曾对 8 个 pi 生态多 agent 框架逐一调研（含 spike 实测），全部不采用：它们都是 coding-agent 形态——子代理为读文件、跑 shell、改代码而生，带工具是它们的卖点，恰好与秘密防火墙正面冲突；它们的杠杆在调度/注册表/并发配额/phase DAG，而这正是这里不需要的部分。采纳任何一个 = 用 5% 框架、对抗 95%。通用定律：**领域不变量越硬，build-vs-buy 越倾向自持薄接缝**——正确性脊柱（台账、审核门）本来就活在 engine 里，底座只需要做好框架反而做不到的一件事：密闭。

接缝可生长而不长成框架，每项都只是几行：

- 持久记忆导演：按阵营 pin `--session-id`，子进程续自己的 transcript。
- swarm：并发 fork N 个导演，session 天然互不污染。
- 跨阵营协调：engine 把一个导演的输出（如 `ordersToAllies`）穿针进另一个的下轮 prompt；GM/canonical state 是唯一共享板。

### pending-harvest 台账：产出的候选不能静默丢失

spawn/harvest 拆成两轮后出现新失败面：GM 忘了收割，或用一个敷衍的 `no-change` 解决掉平行线，**把导演已产出的候选整个扔掉**。义务账（见 `evented-runtime.md` 引擎台账节）只保证「落地了什么」，不保证「收割了这个 run」。对策是第二本账，强制力度照旧对齐可验证性：

- spawn 时记 `{runId, lineId, spawnedAt}` 入账；harvest 按 runId 销账；候选落地按 lineId 销账（覆盖手动落地路径）。
- **牙齿放在丢弃点**：存在未收割 run 时，resolve/丢弃该平行线的工具硬拒，强制先收割——收割后「导演自己说 no-change」的正路仍然通。
- 软层是催办：canonical commit 返回值逐轮列出 pending run，没挂义务的 run 也不会被遗忘。

结果是自愈环：spawn →（催办）→ harvest（销账 + 展示候选与落地指引）→ 落地或解决。engine 拥有读写两端；不要让 GM 自己去 session 目录翻 jsonl（文件名带不可预测时间戳前缀，LLM 做不到），也不要依赖框架的 inspect 工具（它不知道 engine 分叉的进程）。

## 反模式

- 每个 NPC 都拆 agent。
- 子代理持有完整 state。
- 子代理负责修正 GM 遗漏的 patch。
- 子代理拿 `code_act` 或 debug/migration 工具。
- 知密后台导演跑在 in-process 框架里（防不住工具与上下文继承），或子进程不带 `--no-tools --no-approve --no-context-files`。
- 知密子进程的 session 落在非 gitignored 目录。
- 用 subagent 代替工具 description、strict path、migration。
- 单线程场景硬拆并行。
- 候选 subagent 输出 Markdown 长文，迫使 GM 再抽结构。
- subagent 自己读 debug 快照文件当 state 真相源。
