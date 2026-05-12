# 多 Agent 架构：GM + Narrator(s)

## 架构

```
用户输入
   │
   ▼
┌─────────────────────────┐
│  GM agent               │
│  system prompt:          │
│    - 世界设定             │
│    - 规则（≤5条）         │
│    - 当前游戏状态         │
│    - 可用工具             │
│                          │
│  工具:                    │
│    dice, combat, state,  │
│    affection, quest ...  │
│                          │
│  流程:                   │
│    1. 调用游戏工具        │
│    2. 得出结论"发生了什么" │
│    3. 自己决定是否调      │
│       narrator（不强制）   │
│    4. 可选 spawn 多个     │
│       subagent 并行叙事   │
└────────┬────────────────┘
         │ subagent 工具
         ▼
┌─────────────────────────┐
│  Narrator subagent       │
│  system prompt:          │
│    - 纯文风+视角约束       │
│    - 角色设定             │
│    - 无游戏工具           │
│                          │
│  输入:                    │
│    "当前状态: {...}       │
│     机械结果: {...}       │
│     请写出场景叙事"       │
│                          │
│  输出: 纯叙事 prose       │
└─────────────────────────┘
```

**GM 自己决定何时调 narrator，不强制每轮都调。** 一顿骰子和状态更新之后可能一句话带过（GM 自己输出简短叙事），也可能 spawn 多个 subagent 并行——比如一个写主线叙事、一个写 NPC 内心独白、一个写远处的并行事件。agent 的 meta 能力让它自己判断。

## 文件结构

```
project/
├── skills/
│   └── 开局.md                # 开局 setup
├── agents/
│   ├── gm.md                  # GM 的 system prompt
│   └── narrator.md            # 叙事者 subagent 定义
├── engine/                    # TS 引擎模块（平台无关，按需）
│   ├── state.ts               # 事件溯源状态引擎（必有）
│   ├── dice.ts                # 骰子系统
│   ├── combat.ts              # 战斗系统
│   ├── affection.ts           # 好感度系统
│   └── ...                    # economy, quest, death, time... 按需
├── tools/
│   └── registry.ts            # 工具注册
├── data/                      # 世界书拆解数据（按需）
├── state/                     # 运行时（自动创建）
│   ├── events/
│   └── index.json
└── narrator.log               # 纯叙事输出（tail -f 查看）
```

没有战斗系统就不用 `combat.ts`，没有经济系统就不用 `economy.ts`。按卡片实际系统决定。

## agents/narrator.md

`{{}}` 占位符根据卡片内容填入：

```markdown
---
name: narrator
description: 纯叙事生成，输出小说式 prose
tools: []
model:  # 叙事用较好的 model，按需选
---

你是{{world}}世界的叙事者。

## 文风
{{style_guide}}

## 角色
{{character_context}}

## 规则
- 只输出叙事文本，不要调用任何工具
- 严格基于提供的游戏状态和机械结果，不编造未发生的事件
- {{视角约束，如：用第二人称视角}}
- 输出为纯文本，不使用 markdown 标题、代码块
```

## agents/gm.md 骨架

```
# <世界名> — <角色名>

你是 GM。管理游戏状态、执行规则、决定叙事。

## 世界设定
<从世界书提取的核心世界观>

## 规则
1. <最重要的规则，不超过 5 条>
2. ...

## 工具
你可以使用以下工具：
- re0_status: 查看主角面板
- re0_skill_check: 属性检定
- re0_combat: 战斗
- ... <按实际注册的工具列出>

## 叙事
完成机械处理后，用 subagent 工具调用 narrator 生成叙事。
- 简单的状态查询结果可以自己一句话带过
- 重大的剧情推进应该调 narrator
- 可以同时调多个 narrator 并行处理不同视角
```

## GM 胶水层（平台不同，引擎相同）

核心逻辑三件事，`engine/` 是跨平台复用的：

1. **注入 system prompt + 当前游戏状态**（每轮都要，保证状态不陈旧）
2. **注册所有游戏工具**（dice、combat、state 查询/更新等）
3. **捕获 subagent 输出写入 narrator.log**

### pi 实现

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { getCurrentState } from "./engine/state";
import { registerAllTools } from "./tools/registry";

export default function (pi: ExtensionAPI) {
  // 1. 注入 system prompt + 实时状态
  pi.on("before_agent_start", async (event) => {
    const prompt = readFileSync(join(__dirname, "..", "agents", "gm.md"), "utf-8");
    const state = getCurrentState();
    const stateBlock = "\n\n## 当前游戏状态\n```json\n" +
      JSON.stringify(state, null, 2) + "\n```";
    return { systemPrompt: prompt + stateBlock + "\n\n" + (event.systemPrompt || "") };
  });

  // 2. 注册游戏工具
  registerAllTools(pi);

  // 3. 捕获 subagent 输出 → narrator.log
  pi.on("tool_result_end", async (event) => {
    if (event.toolCall?.name === "subagent") {
      const content = event.message?.content;
      if (content && Array.isArray(content)) {
        for (const part of content) {
          if (part.type === "text" && part.text?.trim()) {
            appendFileSync("narrator.log", part.text + "\n\n---\n\n");
          }
        }
      }
    }
  });
}
```

### Claude Code 实现

见 `references/platform-adapters.md`。
