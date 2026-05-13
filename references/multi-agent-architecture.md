# 多 Agent 架构：GM + NPC 上下文隔离

## 要解决的问题

SillyTavern 单一 context 的经典缺陷：模型同时读到所有 NPC 的设定。

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

多 agent 解法：每个有隐秘信息的 NPC 跑在独立 context 里，只能看到自己该知道的信息。

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

## 什么时候用

| 条件 | 决策 |
|------|------|
| NPC ≤4 且无隐藏信息 | 单 agent，GM 自己扮演所有 NPC |
| NPC ≥5 且有隐藏信息/秘密/阵营 | 多 agent，有秘密的 NPC 各一个 subagent |
| NPC 之间信息严重不对等 | 多 agent——上下文隔离的核心价值 |

**多 agent 跟 game engine 复杂度无关。** 零骰子的纯 prompt 卡，如果 NPC 多且有秘密，照样走多 agent。

## 不要用这个模式做的事

- ❌ **GM + Narrator 外包叙事**：把叙事交给 subagent，输出要 Ctrl+O 展开，token 翻倍，GM 失能。narrator 模式只在并行多视角叙事 + 模型分层省钱时有微弱价值。
- ❌ **为每个 NPC 都建 agent**：只有 NPC ≤4 个时，单 agent 更干净。在 GM prompt 里写清楚「每个 NPC 只能基于自己的 setting 行动，不能跨界知道其他 NPC 的秘密」通常就够了。
- ❌ **NPC agent 持有游戏状态**：NPC subagent 不知道 HP、物品、全局 flag。这些是 GM 的职责。

## 实现

### 前置依赖

```bash
pi install npm:pi-subagents
```

### NPC Agent 定义模板

每个需要隔离的 NPC 一个 `.md` 文件，放在 `agents/` 目录，symlink 到 `~/.pi/agent/agents/`（全局作用域）或 `.pi/agents/`（项目作用域）：

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
├── agents/
│   ├── gm.md                  # GM system prompt
│   ├── npc_bartender.md       # 酒保 NPC（有隐藏故事）
│   ├── npc_stranger.md        # 神秘旅人 NPC（有秘密身份）
│   └── npc_bard.md            # 吟游诗人 NPC（消息灵通但不可信）
├── engine/                    # TS 引擎（按需）
├── extensions/
│   └── index.ts               # 胶水层
├── data/
│   ├── world.json             # 世界设定（所有 NPC 的公开信息）
│   └── characters.json        # 角色数据
└── skills/
    └── 开局.md
```

## pi 胶水层要点

```typescript
// extensions/index.ts
pi.on("before_agent_start", async (event) => {
  // 注入 GM prompt + 实时状态
  // GM prompt 中包含 NPC 调用指南
  return { systemPrompt: gmPrompt + stateBlock + npcGuide + (event.systemPrompt || "") };
});
```

NPC agent 通过 `defaultReads: data/world.json` 自动获得世界公开信息。个人的秘密和私密背景直接写在 agent 定义文件里，这段内容不会被其他 NPC 看到。

## 与传统 narrator 模式的对比

| | 旧方案（GM+Narrator） | 新方案（GM+NPC 隔离） |
|------|------|------|
| 谁叙事 | Narrator subagent | **GM 自己** |
| subagent 职责 | 写 prose | **NPC 台词+动作** |
| 输出展示 | Ctrl+O 展开看 | GM 织入主回复，直接可见 |
| token | 叙事文本两份 | NPC 回应只一份 |
| 解决的问题 | （没有真正解决什么） | **上下文污染 → 信息泄漏** |
| 适用场景 | 几乎没用 | 多 NPC、有秘密、信息不对等 |

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
| 多地点同时叙事 | 队伍分头行动。多个 narrator 并行跑，各写各的场景，GM 汇总 |
| 多 NPC 同时反应 | 一个事件发生，多个 NPC 同时反应——并行调多个 NPC agent |

### 反模式——这些不要用 subagent

| 反模式 | 为什么错 |
|--------|---------|
| GM+Narrator 外包叙事 | PoC 已验证：输出折叠、token 翻倍、GM 失能 |
| 简单的规则引擎 | 一个 TS 函数能做的事，别 spawn 进程 |
| 状态存储 | 文件比子进程更可靠、更快 |
| 频繁调用的轻量操作 | subagent 启动一个 pi 进程，延迟不可忽略 |
| 单线程场景拆成并行 | 无并行需求的场景徒增协调复杂度 |
