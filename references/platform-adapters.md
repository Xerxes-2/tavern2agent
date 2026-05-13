# 平台适配

`engine/*.ts`、`data/`、`scripts/` 是跨平台的。不同平台只换胶水层。

## 开场白

由 `skills/开局.md` 处理，详见 `references/setup.md`。agent 首轮 call 开局 skill，pi extension 通过 skill 完成开场。

## pi 职责

| 职责 | pi |
|------|-----|
| System prompt 注入 | `pi.on("before_agent_start")` extension hook |
| 工具注册 | `pi.registerTool(...)` |
| Subagent | pi 自带 `subagent` 工具，定义放 `agents/*.md` |
| 钩子（日志等） | `pi.on("tool_result_end")` |
| 状态文件 | 任意目录，建议 `state/` |

## pi 完整示例

见 `references/multi-agent-architecture.md`。

## 启动命令

```bash
cd project && pi
```
