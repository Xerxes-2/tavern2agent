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
