# pi extension 集成

**tavern2agent 是 pi-native 项目**。不假装跨平台——`extension.ts` 直接挂 pi 的 `pi.on(...)` 钩子和 `pi.registerTool(...)` API，多 agent 走 pi-subagents，回退靠 pi-rewind-hook 这种 pi 扩展。换 host agent 框架（Claude Code / Cursor / aider 等）不是「换胶水层」级别的工作，是重写集成层 + 重新设计 hook 时机 / tool schema / subagent 模型——通常等于从 SKILL.md 决策表往下重做。

`engine/*.ts`、`data/`、`scripts/` 理论上跟平台无关，但只在跑通 pi-native runtime 后才有意义。本文档记录所有 pi 特有的契约、坑、最佳实践。

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

`start.sh` 内置 **`PI_CODING_AGENT_DIR` 隔离方案**——将 pi 的配置目录从 `~/.pi/agent/` 切换到 `.pi/agent/`，首次运行自动初始化该目录（复制全局 auth、创建设置），后续运行完全隔离全局扩展/skills。仅隔离全局，不影响项目自己的 `.pi/extensions/`、`.pi/skills/`、及 `resources_discover` 注册的 skills。

玩家直接 `./start.sh` 进游戏，支持透传参数：

```bash
./start.sh                          # 默认模型
./start.sh --model deepseek/v4-pro  # 指定模型
./start.sh --continue               # 继续上次会话
```

> **注意**：`PI_CODING_AGENT_DIR` 切换配置目录后，pi 不再读取 `~/.pi/agent/settings.json` 中的全局包配置，因此全局安装的 npm 包（如 pi-rewind-hook、pi-subagents、pi-processes 等）也不会自动加载。如需使用这些包，可以用 `./pi install npm:@foo/bar -l` 安装到项目本地（写入 `.pi/settings.json`），或在 `start.sh` 末尾加 `-e` / `--skill` 参数显式加载。详见 `scripts/start.sh` 注释。

> 项目根目录的 `./pi` 包装脚本（模板见 `tavern2agent/scripts/pi`）自动设置 `PI_CODING_AGENT_DIR`，用户可直接 `./pi install npm:@foo/bar -l` 安装包，无需手动 export 环境变量。

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
    return {
      systemPrompt: event.systemPrompt + "\n\n" + gmPrompt,
    };
  });

  // /retry 命令：回退到最后一次用户消息之前重新发送
  pi.registerCommand("retry", {
    description: "撤销上一轮 agent 响应并重新发送最后一条用户消息",
    handler: async (_args, ctx) => {
      await ctx.waitForIdle();

      const entries = ctx.sessionManager.getEntries();
      let lastUserEntryId: string | null = null;
      let lastUserText: string | null = null;

      for (let i = entries.length - 1; i >= 0; i--) {
        const entry = entries[i];
        if (entry.type === "message" && (entry as any).message?.role === "user") {
          lastUserEntryId = entry.id;
          lastUserText = (entry as any).message.content?.[0]?.text;
          break;
        }
      }

      if (!lastUserEntryId || !lastUserText) {
        ctx.ui.notify("没有找到可重试的用户消息", "warning");
        return;
      }

      const result = await ctx.fork(lastUserEntryId, {
        withSession: async (ctx) => {
          ctx.ui.notify("🔄 重试中（已清除上一轮回复）...", "info");
          await ctx.sendUserMessage(lastUserText);
        },
      });

      if (result.cancelled) {
        ctx.ui.notify("重试被取消", "warning");
      }
    },
  });

  registerAllTools(pi);
}
```

## 工具返回值格式（必读）

**pi 工具 `execute` 函数必须返回 `{ content: [{ type: "text", text: "..." }] }` 格式**（OpenAI tool response 标准格式）。返回纯字符串或 plain object 会导致 pi 渲染层崩溃（`getTextOutput` 中 `result.content.filter` 作用在 `undefined` 上）。

### 错误模式（会崩溃）

```typescript
// ❌ 返回 plain object —— pi 渲染层无法处理
async function get_status() {
  return { hp: 100, mp: 50, location: "病房" };
}

// ❌ 返回纯字符串 —— result.content 为 undefined，filter 崩溃
async function get_status() {
  return `HP: 100 | MP: 50 | 位置: 病房`;
}
```

### 正确模式

```typescript
// ✅ 返回 { content: [{ type: "text", text: "..." }] }
async function get_status() {
  const state = loadState();
  const text = `HP: ${state.hp}/100 | MP: ${state.mp}/50 | 位置: ${state.location}`;
  return { content: [{ type: "text", text }] };
}
```

### 兜底安全网（推荐在 registerAllTools 中统一包装）

为避免每个工具手动写 `{ content: [...] }`，可以在注册层加统一 wrapper：

```typescript
export function registerAllTools(pi: Pi) {
  for (const tool of TOOLS) {
    const rawExecute = tool.execute;
    pi.registerTool({
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
      execute: async (toolCallId: string, params: any) => {
        const result = await rawExecute(params);
        const text = typeof result === "string" ? result : JSON.stringify(result, null, 2);
        return { content: [{ type: "text", text }] };
      },
    });
  }
}
```

### 错误模式（会崩溃）

```typescript
// ❌ 返回 plain object —— pi 渲染层无法处理
async function get_status() {
  return { hp: 100, mp: 50, location: "病房" };
}

async function lookup_npc(params: { name: string }) {
  return { found: true, name: params.name, detail: { ... } };
}
```

### 正确模式

**每条工具的 execute 函数应自行将结果格式化为可读文本，包裹在 `{ content: [{ type: "text", text: "..." }] }` 中返回**。不要依赖外部 wrapper 做 `JSON.stringify`——裸 JSON 在游戏过程中可读性差，且破坏叙事沉浸感。

```typescript
// ✅ 返回 { content: [{ type: "text", text: "..." }] }
async function get_status() {
  const state = loadState();
  const text = `HP: ${state.hp}/100 | MP: ${state.mp}/50 | 位置: ${state.location}`;
  return { content: [{ type: "text", text }] };
}

async function lookup_npc(params: { name: string }) {
  const char = characters[params.name];
  if (!char) return { content: [{ type: "text", text: `未找到角色 "${params.name}"。` }] };
  const text = `## ${params.name}\n年龄：${char.age} | 性格：${char.personality}\n外貌：${char.appearance}`;
  return { content: [{ type: "text", text }] };
}

async function roll_dice(params: { sides?: number }) {
  const sides = params.sides || 6;
  const roll = Math.floor(Math.random() * sides) + 1;
  return { content: [{ type: "text", text: `🎲 d${sides} = ${roll}` }] };
}
```

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

