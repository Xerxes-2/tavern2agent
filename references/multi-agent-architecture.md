# 多 Agent 架构：GM + 认知隔离

## 要解决的问题

SillyTavern 单一 context 的经典缺陷：模型同时读到所有它本不该在同一视角下知道的信息——最典型的是所有 NPC 的设定，但同样适用于悬疑题材的凶手身份、未揭晓的真相、玩家尚未推理出的线索。NPC 秘密只是认知隔离需求里最常见的一种。

以 NPC 设定为例：

```
┌────────────── 单一 context ──────────────┐
│ NPC_A 设定：暗恋公主，只有她知道            │
│ NPC_B 设定：商人，爱打听                   │
│ NPC_C 设定：公主本人                       │
│                                            │
│ 模型看到所有设定 → B 可能"不经意"说出 A     │
│ 的秘密，C 知道她不该知道的事                │
└────────────────────────────────────────────┘
```

多 agent 解法：每个需要认知隔离的视角跑在独立 context 里，只能看到自己该知道的信息——有隐秘信息的 NPC 是一种，"答案不能泄漏给叙事者"的隐藏真相（凶手、阴谋、未揭晓剧情）也是一种。

## 架构

```
用户输入
  │
  ▼
┌─────────────────────────────────────────┐
│  GM agent（主叙事 + 规则 + 世界状态）      │
│  agents/gm.md                           │
│                                          │
│  工具:                                   │
│    dice, combat, state, get_status ...   │
│    subagent（调用 NPC agent）             │
│                                          │
│  叙事流程:                                │
│    1. 玩家行动 → GM 处理规则/掷骰         │
│    2. GM 判断哪些 NPC 需要响应            │
│    3. GM 调对应 NPC subagent              │
│    4. GM 把 NPC 台词/动作织入主叙事        │
│    5. GM 自己继续叙事和场景描写            │
└──────────┬──────────────────────────────┘
           │ subagent 工具
           ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│  npc_xxx subagent        │  │  npc_yyy subagent        │
│  agents/<name>.md        │  │  agents/<name>.md        │
│                           │  │                           │
│  上下文只包含:             │  │  上下文只包含:             │
│  · 该 NPC 的人物设定       │  │  · 该 NPC 的人物设定       │
│  · 该 NPC 知道的公开信息   │  │  · 该 NPC 知道的公开信息   │
│  · 该 NPC 的秘密（如果有）  │  │  · 该 NPC 的秘密（如果有）  │
│  · 当前场景中与它相关的事   │  │  · 当前场景中与它相关的事   │
│                           │  │                           │
│  ❌ 看不到其他 NPC 的秘密   │  │  ❌ 看不到其他 NPC 的秘密   │
│  ❌ 看不到完整世界状态      │  │  ❌ 看不到完整世界状态      │
│                           │  │                           │
│  输出: 台词 + 动作 + 反应   │  │  输出: 台词 + 动作 + 反应   │
└──────────────────────────┘  └──────────────────────────┘
```

## 实战经验：subagent 不是“再开一个万能助手”

经过完整项目实跑后，推荐把 subagent 拆成四层：

```txt
agent prompt       = 稳定职责 / 输出格式 / 角色边界
subagent extension = 当前人格、状态切片、世界摘要等动态事实
task               = 本轮触发原因 / 最近事件重点
chat history       = 叙事脉络（fork/defaultContext 时可见）
```

这样 GM 不需要每次给子代理手写完整上下文，也不需要让子代理先调用工具“自查自己是谁”。子代理进入时就已经拥有当前身份和必要状态，只需完成本轮小任务。

**不要把实现细节写进角色知识。** 注入出来的段落应像自然事实：

```md
## 人格
<当前核心/队友的人格设定>

## 当前感知
<玩家状态、地点、任务、关系摘要>
```

不要写：

```md
这是 extension 自动注入的 system prompt……
```

子代理不需要知道“注入机制”；它只需要知道角色事实。

### 推荐文件结构

```txt
project/
├── .pi/agents/
│   ├── companion.md
│   └── news-writer.md
├── extensions/
│   └── subagents/
│       ├── common.ts          # 公共状态摘要、轻量工具注册
│       ├── companion.ts       # companion 专属注入
│       └── news-writer.ts     # news-writer 专属注入
└── tools/
    └── registry.ts
```

每个 `.pi/agents/*.md` 的 frontmatter 指向自己的 extension：

```yaml
---
name: news-writer
description: 生成世界新闻与酒馆传闻
tools: lookup,get_status
extensions: ./extensions/subagents/news-writer.ts
systemPromptMode: replace
---
```

### 子代理 extension 职责

- 注册该子代理需要的**轻量工具集**，不要继承主 GM 的全量工具。
- 在 `before_agent_start` 读取 state，构造短摘要。
- 只注入这个子代理需要知道的切片：companion 看人格/玩家状态，news-writer 看世界时间/地点/任务/近闻。
- 读取失败时给安全退路：例如 companion 无当前人格时只输出 `（沉默）`。
- 不向子代理暴露实现词：`extension`、`system prompt`、`subagent-tools` 等。

### GM 调用方式

GM 的 task 应短，只补“最近发生了什么/为什么叫你”：

```typescript
subagent({
  agent: "news-writer",
  task: "近期重点：玩家完成灰咳活捉任务，公会正在改写档案。请生成三栏新闻。",
})
```

不要把地点、时间、DLC、任务列表全部塞进 task；这些应由子代理 extension 从 state 注入。task 负责近因，state 负责当前事实，聊天历史负责叙事脉络。

### 内置 coding subagent 的处理

`pi-subagents` 自带 reviewer/worker/oracle 等 coding agents。互动卡发布给玩家时通常不希望它们出现在运行时。推荐在 `start.sh` 的项目隔离 settings 里按模式控制：

```bash
./start.sh                    # 玩家模式：disableBuiltins=true
TAVERN2AGENT_DEV=1 ./start.sh # 开发模式：保留内置 agents
```

不要把开发者自己的全局 subagent 配置当作玩家运行前置条件。

## 什么时候用

这张表只判断 subagent 需求，不判断卡片系统复杂度。无骰子、无 state 的纯 prompt 卡，只要有信息隔离/角色分离/进程隔离，也可以使用 subagent；反过来，战斗经济很复杂但没有隔离需求，也未必需要 subagent。

| 条件 | 决策 |
|------|------|
| NPC 不多（经验阈值 ~4）且无隐藏信息、无隐藏真相 | 单 agent，GM 自己扮演所有 NPC |
| NPC 较多（经验阈值 ~5）且有隐藏信息/秘密/阵营 | 多 agent，有秘密的 NPC 各一个 subagent |
| 视角间信息严重不对等（NPC 之间、PC 之间） | 多 agent——认知隔离的核心价值 |
| 悬疑/侦探等"答案不能泄漏给叙事者"的题材 | 多 agent，真相/凶手视角独立 context，GM 只拿到该揭晓的部分 |

**多 agent 跟 game engine 复杂度无关。** 零骰子的纯 prompt 卡，只要有认知隔离需求（NPC 秘密、隐藏真相、信息不对等），照样走多 agent。

> 4/5 是经验阈值——单 context 同时维持 5+ 套有秘密的人设容易串味（一个 NPC 的暗藏动机会"渗透"到另一个的台词里）。NPC 数少时单 agent 靠 prompt 约束就够，多了就该上隔离。具体阈值因模型而异，临界情况倾向用隔离。

## 不要用这个模式做的事

- ❌ **为每个 NPC 都建 agent**：只有 NPC ≤4 个时，单 agent 更干净。在 GM prompt 里写清楚「每个 NPC 只能基于自己的 setting 行动，不能跨界知道其他 NPC 的秘密」通常就够了。
- ❌ **NPC agent 持有游戏状态**：NPC subagent 不知道 HP、物品、全局 flag。这些是 GM 的职责。

## 实现

### 前置依赖

把 pi-subagents 声明到项目根 `.pi/settings.json`，让 pi 首次启动自动安装到项目本地 `.pi/npm/`：

```json
{
  "packages": [
    "npm:pi-subagents"
  ]
}
```

如果同时需要回退扩展，把 `"npm:pi-rewind-hook"` 放进同一个 `packages` 数组。不要要求玩家手动安装项目级扩展；发布物应直接包含 `.pi/settings.json`。

### NPC Agent 定义模板

每个需要隔离的 NPC 一个 `.md` 文件，发布用项目作用域放在 `.pi/agents/`；如需在源码中另保留一份，可从 `agents/` 复制/同步过去：

```markdown
---
name: npc_<名字>
description: <NPC 简要描述>
tools:
systemPromptMode: replace
defaultReads: data/world.json
---

你是{{世界名}}中的 {{NPC 名字}}。

## 你的设定
<NPC 的完整背景、性格、外貌、秘密>

## 你知道的信息
<这个 NPC 应该知道的事情——公开信息 + 秘密>

## 你不知道的信息
<明确列出不该知道的事——其他 NPC 的秘密、全局状态等>

## 行为规则
- 只输出你的台词和动作，不要叙事，不要描写场景
- 不能说出你不知道的信息
- 基于 GM 传来的当前情境做出自然反应
- 输出为纯文本，格式：「动作描写」+ "对话内容"
```

### GM 调用 NPC Agent

在 GM 的 system prompt 中指导：

```
## NPC 调用
当玩家与 NPC 互动时，用 subagent 工具调用对应的 NPC agent：

  subagent({ agent: "npc_<名字>", task: "当前场景：... 玩家对你说：... 请做出反应。" })

NPC agent 返回台词和动作后，你将其织入主叙事，自己负责场景描写和推进。
可以并行调用多个 NPC（如酒吧场景多人同时反应）。
```

### 文件结构

```
project/
├── .pi/
│   ├── settings.json          # packages: ["npm:pi-subagents", ...]
│   └── agents/                # pi-subagents 项目级 agent 定义
│       ├── npc_bartender.md   # 酒保 NPC（有隐藏故事）
│       ├── npc_stranger.md    # 神秘旅人 NPC（有秘密身份）
│       └── npc_bard.md        # 吟游诗人 NPC（消息灵通但不可信）
├── agents/
│   └── gm.md                  # GM system prompt
├── engine/                    # TS 引擎（按需）
├── extension.ts               # pi extension 入口
├── data/
│   ├── world.json             # 世界设定（所有 NPC 的公开信息）
│   └── characters.json        # 角色数据
└── skills/
    └── start-game/
        └── SKILL.md
```

## pi extension 集成要点

```typescript
// extension.ts
pi.on("before_agent_start", async (event) => {
  // 注入 GM prompt + 实时状态
  // GM prompt 中包含 NPC 调用指南
  return { systemPrompt: gmPrompt + stateBlock + npcGuide + (event.systemPrompt || "") };
});
```

NPC agent 通过 `defaultReads: data/world.json` 自动获得世界公开信息。个人的秘密和私密背景直接写在 agent 定义文件里，这段内容不会被其他 NPC 看到。

---

## 附录：subagent 全场景适用性判断

判断标准：**该角色不该看到的东西**（信息隔离）、**跟 GM 完全不同的人格/文风**（角色分离）、**适合异步/并行的事**（进程隔离）。三者至少占一个才用 subagent。

### 一、信息隔离型（核心价值）

| 场景 | 隔离什么 | 为什么不用单 agent |
|------|----------|-------------------|
| NPC 秘密 | 每个 NPC 的隐藏背景、阵营、真实意图 | 单 context 会泄漏——模型读到 NPC_A 的秘密，会让 NPC_B 无意中"猜到" |
| PC 信息不对等 | 不同玩家角色知道不同的事 | 单 context 里 A 知道的信息会污染 B 的决策 |
| GM 隐藏剧情 | 幕后阴谋、未揭晓的真相 | 连 GM 的主 context 都不该看到完整剧本，否则会"剧透式叙事" |

### 二、角色分离型

| 场景 | 为什么适合 subagent |
|------|---------------------|
| 反派 AI | 反派的 prompt 和 GM 完全不同——GM 是公正裁判，反派应该自私、欺骗。塞同一个 context 会让两种人格互相污染 |
| 队友 AI | 类似 NPC 隔离但更忠诚——队友有独立性格但忠于玩家，prompt 风格介于 GM 和 NPC 之间 |
| 吟游诗人/旁白 | 需要不同**文风模式**。GM 写规则化文本，旁白需要诗化、模糊、氛围化。两个 prompt 混在一起两头不讨好 |

### 三、进程隔离型

| 场景 | 为什么适合 subagent |
|------|---------------------|
| 战斗结算器 | 复杂战斗逻辑（掷骰→查表→计算伤害→判断死亡）需要严格确定性。subagent 专做此事，GM 只收结果 |
| 经济/物价模拟 | 动态经济系统可异步跑，GM 查一下就拿到结果 |
| 章节存档校验 | 每章结束时检查 flag 一致性——"这个 NPC 第 3 章死了但第 5 章又出现了？" |

### 四、并行天然适合

| 场景 | 说明 |
|------|------|
| 多地点同时叙事 | 队伍分头行动。多个场景并行推进，GM 汇总 |
| 多 NPC 同时反应 | 一个事件发生，多个 NPC 同时反应——并行调多个 NPC agent |

### 五、状态更新不是 subagent 的默认职责

状态变化优先下沉到专用工具、strict patch、state schema 校验、attention 提醒和工具 description。不要为了弥补 GM 偶尔忘记 patch 就新增一个状态子代理；这会引入额外延迟和职责重叠。

如果某类状态变化有明确规则，写专用工具；如果是低频条件提醒，写 attention；如果是非法路径，写 schema/strict path。subagent 只在信息隔离、角色分离、进程隔离确实成立时使用。

### 反模式——这些不要用 subagent

| 反模式 | 为什么错 |
|--------|---------|
| 简单的规则引擎 | 一个 TS 函数能做的事，别 spawn 进程 |
| 状态存储 | 文件比子进程更可靠、更快 |
| 频繁调用的轻量操作 | subagent 启动一个 pi 进程，延迟不可忽略 |
| 单线程场景拆成并行 | 无并行需求的场景徒增协调复杂度 |
