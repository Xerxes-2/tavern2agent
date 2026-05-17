# 平台适配

`engine/*.ts`、`data/`、`scripts/` 是跨平台的。不同平台只换胶水层。

## 开场白

由开局 skill 处理（详见 `references/setup.md`）。agent 首轮 call 开局 skill。

> **注意**：`skills/` 不在 pi 默认技能发现路径中。extension 必须通过 `resources_discover` 钩子注册技能路径，否则开局 skill 不会被 pi 加载。详见下方「技能路径注册」。

## pi 职责

| 职责 | pi |
|------|-----|
| System prompt 注入 | `pi.on("before_agent_start")` extension hook |
| 工具注册 | `pi.registerTool(...)` |
| 技能路径注册 | `pi.on("resources_discover")` — 注册 `skills/` 目录，pi 递归发现其中的 `<name>/SKILL.md` 技能文件 |
| NPC 上下文隔离 | `pi-subagents` 包，定义放 `agents/*.md`。常用于 NPC 信息隔离，防止秘密泄漏 |
| 钩子（日志等） | `pi.on("tool_result_end")` |
| 状态文件 | 任意目录，建议 `state/` |

## 启动脚本

每个转换产出的项目目录**必须**包含 `start.sh`，模板见 `tavern2agent/scripts/start.sh`，迁移时直接复制到项目根目录并 `chmod +x`。

模板已内置 `-ne -ns`（隔离外部扩展/技能），玩家直接 `./start.sh` 进游戏，支持透传参数：

```bash
./start.sh                          # 默认模型
./start.sh --model deepseek/v4-pro  # 指定模型
./start.sh --continue               # 继续上次会话
```

## extension 加载限制 + 技能路径注册（必读）

pi 通过 **jiti** 加载 `extension.ts`，几个坑：

- **不要用动态 `import()`**——jiti 下行为不稳，所有依赖必须**顶层 `import`**（包括 `engine/state`、`tools/registry`、`engine/dice` 等）
- **不要用 top-level await**——同样 jiti 兼容性问题，初始化逻辑写进 `before_agent_start` 钩子
- **路径用相对 `./` 或 `../` 可能按 `cwd` 解析**——对外部文件和 `resources_discover` 路径注册一律用绝对路径，通过 `import.meta.url` 获取当前文件目录
- **环境变量在 extension 顶层读取一次缓存**——别在工具 execute 里反复 `process.env.X`

**技能路径注册**：pi 默认只从 `~/.pi/agent/skills/` 和 `.pi/skills/` 发现技能。项目自己的 `skills/` 需要通过 `resources_discover` 显式注册。pi 扫描注册目录时查找 `<name>/SKILL.md` 子目录结构（name 必须 ASCII a-z/0-9/-，且与目录名一致）：

```typescript
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

pi.on("resources_discover", async () => {
  return { skillPaths: [join(__dirname, "skills")] };
});
```

extension 入口契约：只做平台注册（system prompt 注入 + 技能路径注册 + 调用 `registerAllTools(pi)` + 必要 hooks），**不要在 extension.ts 里内联工具实现**——工具一律放 `tools/registry.ts`，否则 registry.ts 变死代码。

最小骨架：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerAllTools } from "./tools/registry";
import { snapshotBeforeTurn } from "./engine/state";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default function extension(pi: ExtensionAPI) {
  // 技能路径注册（pi 递归扫描 skills/ 发现 <name>/SKILL.md）
  pi.on("resources_discover", async () => {
    return { skillPaths: [join(__dirname, "skills")] };
  });

  const gmPrompt = readFileSync(join(__dirname, "agents", "gm.md"), "utf-8");
  pi.on("before_agent_start", async (event) => {
    snapshotBeforeTurn(event.prompt); // 用 prompt 做简易 turn 标识
    return {
      systemPrompt: event.systemPrompt + "\n\n" + gmPrompt,
    };
  });
  registerAllTools(pi);
}
```

## 工具 description 工程（必读）

> 这是从 DeepSeek V4 适配中验证出来的关键发现：**function calling 模式下，模型决定是否调用工具，主要读工具的 `description` 字段，不是 system prompt。** 对所有模型通用，只是措辞强度需微调。

### 问题

强叙事模型（DeepSeek V4、Claude Opus 等）叙事能力越强，越倾向于「自己编」而不是「调工具查」。实测中：
- 写入类工具（`patch_state`）模型会主动调——叙事中发生了 X，所以要写入 X
- 读取类工具（`lookup_location`、`get_price`、`combat_attack`）完全不用——模型觉得自己「记得」设定、能「推断」价格、能「编」战斗数值

根因：模型的内部权衡是「继续写 vs 停下来查」，叙事流畅度的梯度更强。它默认"打断叙事 = 大代价，编一个 = 小代价"。

### 核心方案：把工具 description 当作执行手册而不是元数据

不要假设模型会从 system prompt 的泛泛要求里自行推导调用时机。必须在**每一个工具的 description 字段**里写清楚三件事：

```
description: "功能简述。\n\n【必须调用的场景】\n- 具体场景 1\n- 具体场景 2\n\n【严禁的行为】\n- 禁则\n\n【你的职责】（可选，用于框架重定位）\n- 你不是创造者，你是翻译者"
```

### 模板

**查询类工具**（地点/NPC/价格/任务）：

```typescript
pi.registerTool({
  name: "lookup_location",
  description: "检索世界书中关于地点的权威设定。这是地点信息的唯一权威来源。\n\n" +
    "【必须调用的场景】\n" +
    "- 玩家进入或提及任何城镇/区域/地标\n" +
    "- 需要描述某个地点的环境氛围、设施时\n\n" +
    "【严禁的行为】\n" +
    "- 凭记忆描述地点——你的内部记忆对预设地点的细节不可靠，编造的细节会与后续设定冲突\n" +
    "- 即兴编造地点名——先查索引确认是否存在",
  // ...
});
```

**战斗类工具**（攻击检定/NPC 生成）：

```typescript
pi.registerTool({
  name: "combat_attack",
  description: "执行一次完整攻击检定（掷骰→评级→伤害计算），这是战斗结果的唯一权威来源。\n\n" +
    "【必须调用的场景】\n" +
    "- 任何攻击命中/未命中的判定\n" +
    "- 任何伤害数值的产生\n" +
    "- 任何技能效果的触发\n\n" +
    "【严禁的行为】\n" +
    "- 自行叙述「造成 15 点伤害」这类带具体数值的内容\n" +
    "- 跳过检定直接描述战斗结果\n\n" +
    "【你的职责】\n" +
    "你不是战斗结果的创造者，你是战斗结果的翻译者。此工具返回机械数据，你将数据转为生动的叙事描写。",
  // ...
});
```

### system prompt 配合："机械层 vs 叙事层" 双层框架

除了工具 description，system prompt 也需要配合——不是写触发表，而是重新定义"不调工具"的代价：

```
你的输出由两层构成：
① 机械层 — 由工具调用确定。所有具体数据、设定、判定结果必须来自工具返回值。
② 叙事层 — 由你生成。将机械层结果翻译为生动的描写。

机械层的任何内容**未经工具调用确认前不存在**。
如果你在没有调用相应工具的情况下叙述了这些内容，你就是在污染游戏状态。
这比「叙事节奏稍慢」严重得多。
```

关键：把"不调就编"重新框定为**污染游戏状态**，而不是"偷懒"或"拖慢节奏"。这对强叙事模型的内部决策权重影响最大。

### few-shot 示例（system prompt 末尾）

DS V4 等模型对示例的模仿倾向远强于对指令的遵循。放一个完整示例：

```
# 示例

用户：「我走进公会装备店，想买一把短剑和一瓶治疗药剂。」

【正确行为】
1. 先调 lookup_location("公会装备店") 确认店铺设定
2. 调 get_price(category="武器", quality="普通") 获取短剑价格
3. 调 get_price(category="药剂", quality="普通") 获取治疗药剂价格
4. 调 get_status 确认玩家当前金钱
5. 基于以上信息进行叙事

【错误行为 — 严禁】
直接叙述：「店主从墙上取下一把短剑，『300G，不二价。』你又拿了瓶治疗药剂，80G。」
（错误原因：价格全部未经工具确认，是在污染游戏经济状态。）
```

