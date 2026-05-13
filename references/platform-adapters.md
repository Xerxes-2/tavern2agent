# 平台适配

`engine/*.ts`、`data/`、`scripts/` 是跨平台的。不同平台只换胶水层。

## 开场白

由 `skills/开局.md` 处理，详见 `references/setup.md`。agent 首轮 call 开局 skill，pi extension 通过 skill 完成开场。

## pi 职责

| 职责 | pi |
|------|-----|
| System prompt 注入 | `pi.on("before_agent_start")` extension hook |
| 工具注册 | `pi.registerTool(...)` |
| NPC 上下文隔离 | `pi-subagents` 包，定义放 `agents/*.md`。常用于 NPC 信息隔离，防止秘密泄漏 |
| 钩子（日志等） | `pi.on("tool_result_end")` |
| 状态文件 | 任意目录，建议 `state/` |

## pi 完整示例

见 `references/multi-agent-architecture.md`。

## 启动命令

```bash
cd project && pi
```

## extension 加载限制（必读）

pi 通过 **jiti** 加载 `extension.ts`，几个坑：

- **不要用动态 `import()`**——jiti 下行为不稳，所有依赖必须**顶层 `import`**（包括 `engine/state`、`tools/registry`、`engine/dice` 等）
- **不要用 top-level await**——同样 jiti 兼容性问题，初始化逻辑写进 `before_agent_start` 钩子
- **路径用相对 `./` 或 `../`，带 `.ts` 后缀照写**——jiti 会处理，不要手动改 `.js`
- **环境变量在 extension 顶层读取一次缓存**——别在工具 execute 里反复 `process.env.X`

extension 入口契约：只做平台注册（system prompt 注入 + 调用 `registerAllTools(pi)` + 必要 hooks），**不要在 extension.ts 里内联工具实现**——工具一律放 `tools/registry.ts`，否则 registry.ts 变死代码。

最小骨架：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerAllTools } from "./tools/registry";
import { snapshotBeforeTurn } from "./engine/state";
import { readFileSync } from "node:fs";

export default function extension(pi: ExtensionAPI) {
  const gmPrompt = readFileSync("./agents/gm.md", "utf-8");
  pi.on("before_agent_start", (e) => {
    pi.injectSystemPrompt(gmPrompt);
    snapshotBeforeTurn(e.turnId);
  });
  registerAllTools(pi);
}
```
