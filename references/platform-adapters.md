# 平台适配

`engine/*.ts`、`data/`、`scripts/` 是跨平台的。不同平台只换胶水层。

## 开场白

由 `skills/开局.md` 处理，详见 `references/setup.md`。agent 首轮 call 开局 skill，pi extension 和 Claude Code 均通过 skill 完成开场。

## 职责对照

| 职责 | pi | Claude Code |
|------|-----|-------------|
| System prompt 注入 | `pi.on("before_agent_start")` extension hook | `CLAUDE.md` 文件，或用 `/init` 加载 `agents/gm.md` |
| 工具注册 | `pi.registerTool(...)` | MCP server 的 `tools/list` + `tools/call` |
| Subagent | pi 自带 `subagent` 工具，定义放 `agents/*.md` | `task` 工具，agent 定义放 `.claude/agents/` |
| 钩子（日志等） | `pi.on("tool_result_end")` | `hooks.json` 中的 `PostToolUse` |
| 状态文件 | 任意目录，建议 `state/` | 同左 |

## Claude Code 完整示例

### 1. agents/ 放到 .claude/

```
project/
├── .claude/
│   └── agents/
│       ├── narrator.md       # 内容同 agents/narrator.md
│       └── gm.md             # 内容同 agents/gm.md
├── engine/                   # 同 pi
├── tools/                    # 同 pi
├── data/                     # 同 pi
└── state/                    # 同 pi
```

### 2. CLAUDE.md

```markdown
# 角色扮演模式

当用户开始游戏时，加载 `.claude/agents/gm.md` 作为 system prompt。
每轮开始时读取 `state/state.json` 获取最新游戏状态。

可用 MCP 工具：
- dice-server: 掷骰、属性检定
- combat-server: 战斗、伤害计算
- state-server: 状态查询、更新、回溯
```

### 3. MCP server 示例

游戏工具做成 MCP server，tool handler 直接 import engine。SDK 用 `@modelcontextprotocol/sdk`（不是 `@anthropic-ai/sdk`）：

```typescript
// mcp-server.ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { getCurrentState, dispatch, rollback } from "./engine/state";
import { check, calcDamage } from "./engine/dice";

const server = new McpServer({ name: "re0-game-engine", version: "1.0.0" });

server.tool("re0_status", "查看主角完整面板", {}, async () => {
  const state = getCurrentState();
  return { content: [{ type: "text", text: JSON.stringify(state.主角, null, 2) }] };
});

server.tool(
  "re0_skill_check",
  "属性检定",
  {
    attribute: z.string().describe("属性名"),
    difficulty: z.enum(["简单", "普通", "困难", "极难", "噩梦"]).optional(),
  },
  async ({ attribute, difficulty }) => {
    const state = getCurrentState();
    const attrs = (state.主角 as Record<string, unknown>).属性列表 as Record<string, number>;
    const dcMap: Record<string, number> = { 简单: 8, 普通: 12, 困难: 16, 极难: 20, 噩梦: 25 };
    const dc = dcMap[difficulty ?? "普通"];
    const result = check(attrs[attribute] ?? 10, dc);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
);

// ... 其他工具

await server.connect(new StdioServerTransport());
```

注册到 Claude Code：在项目根的 `.mcp.json` 中加入 `{ "mcpServers": { "re0": { "command": "node", "args": ["mcp-server.js"], "env": { "TAVERN2AGENT_STATE_DIR": "state" } } } }`。

### 4. hooks.json（写入 narrator.log）

写一个独立 `scripts/capture_narrative.py`：从 stdin 读 `$CLAUDE_TOOL_OUTPUT` 的 JSON，遍历 `content[]` 把 `type == "text"` 的文本 append 到 `narrator.log`，结尾追加 `\n---\n`。

然后 hooks.json：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "task",
        "hooks": [
          { "type": "command", "command": "python3 scripts/capture_narrative.py" }
        ]
      }
    ]
  }
}
```

不要把整段 Python 内联进 `command` 字符串——转义噩梦，且不可单独测试。

### 5. 三个平台的启动命令

```bash
# pi
cd project && pi

# Claude Code
cd project && claude

# 另一个终端：纯叙事流
tail -f project/narrator.log
```

## pi 完整示例

见 `references/multi-agent-architecture.md`。
