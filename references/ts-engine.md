# TS 引擎

运行时 engine 用 TypeScript，供 pi extension 直接 import。本文只写稳定契约，不给可无脑复制的大骨架。

标准方案的战斗/骰子/经济通常进 CodeAct 沙箱；本文主要是 light 和 standard 共用的 state 基建。

## State 契约

- `INITIAL_STATE` + schema 是当前唯一结构。
- 旧字段只在 migration 里读，运行时不长期 fallback。
- 派生值运行时计算，不落盘。
- 所有写入走 engine 函数；LLM 不直接改对象。
- 写入返回结构化结果，方便叙事和测试。
- schema 变更要 bump version + deterministic migration。

## 持久化模型

```txt
pi session custom entry   真相源，跟随 session 分支
        ↓ hydrate
in-memory/global store    工具和沙箱读写
        ↓ export
state/state.json          debug / 旧存档导入，不发布
```

读档、回退、章节存档用 pi session tree/fork。不要自建事件溯源回滚系统。

## state.ts 应提供

```txt
hydrate(branchEntries)
getState()                 返回 clone
writeState(next)
patchState(ops)             带 strict/protected path 检查
getStateSnapshot()
isDirty()/markPersisted()
incrementTurnCount()
```

实现细节可按项目调整，但接口语义保持稳定。

## session hooks

extension 负责：

- session start/tree：从当前分支最近 snapshot hydrate。
- turn start / agent end：dirty 时 append snapshot。
- session compact：压缩后补当前 snapshot 锚点。
- mutating tool 结束：把 snapshot 放进 tool result details，便于日志和恢复。

不要求每个项目复制同一份代码；只要满足上述语义。

## JSON Patch

light 方案可暴露 `patch_state`。要求：

- 只传变化，不传整棵 state。
- JSON Pointer 路径必须受 schema/root 白名单保护。
- 有专用工具/组合函数负责的路径禁止裸 patch。
- RFC 6902 的 `replace` 只能改已存在路径；初始化时要先建全字段。

standard 方案中，`patch` 是 CodeAct 原语，仍受相同保护。

## 永久记忆

只有死亡循环/周目继承类机制需要跨 session 回退保留字段。

可选实现：

- `meta/persistent.json`，进 `.gitignore`。
- 或独立 permanent custom entry。

无此机制就不要加。

## 调试日志

可记录 patch JSONL 供人工排查，但不要把它当读档源。

```txt
patches.jsonl = debug log, not source of truth
```

## 轻量 attention

标准 CodeAct 不写 `attention.ts`；GM 可在沙箱里 `status()` 后自行 log 张力点。

light 方案若需要“每 N 轮提醒同伴 / XP 溢出提醒”，可以写 `buildReminders(state)`，在每轮 prompt 注入。

规则：

- reminder 是提示，不是事实源。
- 关键约束仍放工具/engine。
- 不要用 attention 弥补坏 schema 或坏工具设计。

## 工具注册

`tools/registry.ts` 是工具入口；`extension.ts` 只调用 `registerAllTools(pi)`。

工具原则：

- execute 直接调 engine 函数，不 spawn 子进程。
- 参数 schema 简洁。
- 返回 content 给模型，details 给 TUI/日志。
- mutating tool 统一附带 state snapshot。
- light 常见：`get_status`、`patch_state`、少量专用工具。
- standard 常见：`code_act`、`get_status`、`lookup`、`switch_toolset`。

## 测试

至少测：

- hydrate 从 session snapshot 恢复。
- patch 拒绝非法 root / protected path。
- migration 把旧 fixture 升到当前 schema。
- mutating tool 会产生 snapshot。
- session compact 后有新锚点。

## 禁区

- 复制示例字段当 schema。
- 把 `state/state.json` 当真相源。
- 在运行时兼容多代旧字段。
- 让 GM 手写 migration patch。
- 标准方案再生成一堆独立 dice/combat/economy 工具。
