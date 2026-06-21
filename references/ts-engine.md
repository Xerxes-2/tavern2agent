# TS 引擎

运行时 engine 用 TypeScript，供 pi extension 直接 import。本文只写稳定契约，不给可无脑复制的大骨架。

标准方案的战斗/骰子/经济通常进 CodeAct 沙箱或 typed deep tools；本文主要是 light 和 standard 共用的 evented state 基建。CodeAct 不是 state 真相源；它提交领域事件或调用同一套 domain API。

## State 契约

- `INITIAL_STATE` + schema 是当前唯一结构。
- 旧字段只在 migration 里读，运行时不长期 fallback。
- 身份建模成 role/facet，不建 actor kind。主角是 `protagonistActorId` 指向的角色；契约身份是可得可失的 role 字段；特殊形态是可挂载的 facet 对象。为每种身份造实体子类型，后面必然出现「既是 A 又是 B」的角色塞不进去。
- 派生值运行时计算，不落盘。
- 所有写入走领域事件、engine 函数或 CodeAct domain API；LLM 不直接改对象。
- 写入返回 domain event、before/after 摘要和叙事 hook，方便审计、叙事和测试。
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

## 模块切分

不要把类型、store、持久化、归一化堆进一个 `state.ts` 杂物抽屉。按职责分文件：

```txt
state.ts             纯类型词汇表，零函数
state-store.ts       store 生命周期：hydrate / getState / commit / reset
state-persistence.ts session custom entry 读写胶水
ids.ts               ID 分配（扫描 draft，不用模块级计数器）
turn-log.ts          turn / event 日志
共享归一化模块        unknown → typed input 的边界校验（见 tool-abstraction）
```

`engine/events.ts` 定义 event catalog；`engine/reducers.ts` 实现状态变化。工具和 CodeAct API 不应绕过 reducer。

## 领域事件纯化 + 单一写入者

领域事件函数形态固定为 `(draft, event)`：收一个 draft state，只改这个 draft。领域逻辑里禁止 `getState()` / `updateState()` / 模块级可变量。

store 的写入收口到一个 Domain Event Tool Runner，它是唯一写入者，执行顺序固定：

```txt
clone draft ← store
→ 领域事件改 draft
→ schema 校验
→ commit 进 store
→ 持久化 session entry
→ snapshot 附进 tool details
→ 返回玩家安全文本
```

事件抛错 = 丢弃 draft，store 原样。不需要事务回滚机制；「失败即不提交」就是回滚。

禁止嵌套写入。fsn 曾在一次 `updateState` 回调里再调一次 `updateState`，外层 commit 把内层产生的 offscreen 事件覆盖丢失。单一 runner 收口后这类 bug 无处发生。

纯化的红利：领域事件可以直接构造 draft 喂参数做单测，不需要 `resetState()` 仪式；`createId` 扫描 draft 分配，同一次 commit 内不撞 ID，测试之间 ID 不漂移。

## Projection 按消费者建

state projection 按具体消费者命名和裁剪：GM brief、玩家状态面板、subagent context、compaction digest。每个 builder 只从 public slice 取数；不要写一个通用 "format state" 壳再到处复用。有 secret 边界的项目，给每个 projection 写「不含 secret 字段」的测试。

## session hooks

extension 负责：

- session start/tree：从当前分支最近 snapshot hydrate。
- turn start / agent end：dirty 时 append snapshot。
- session compact：压缩后补当前 snapshot 锚点。
- mutating tool 结束：把 snapshot 放进 tool result details，便于日志和恢复。

不要求每个项目复制同一份代码；只要满足上述语义。

## JSON Patch

`patch_state` 只用于 debug/setup/migration，description 标明 debug-only。若项目保留它，要求：

- 只传变化，不传整棵 state。
- JSON Pointer 路径必须受 schema/root 白名单保护。
- 受保护路径清单见 `references/evented-runtime.md` 的 Patch 纪律。
- RFC 6902 的 `replace` 只能改已存在路径；初始化时要先建全字段。

standard 方案中，`patch` 若作为 CodeAct 原语存在，也必须 debug-only 或受相同保护；常规玩法脚本优先调用 domain API。

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

若需要「每 N 轮提醒同伴 / XP 溢出提醒」，可以写 `buildReminders(state)`，在每轮 prompt 注入。

规则：

- reminder 是提示，不是事实源。
- 关键约束仍放工具/engine。
- 不要用 attention 弥补坏 schema 或坏工具设计。

## 工具注册

每个工具一个文件，导出完整定义：name、description、parameters、execute 同文件。`tools/registry.ts` 只是注册清单（import 各定义、循环注册），`extension.ts` 只调用 `registerAllTools(pi)`。

fsn 把契约集中在 registry 时，registry 长到 1087 行，改一个工具要跨文件对照参数和实现；合并后 registry 剩 60 行。registry 测试至少做三件事：遍历所有工具文件断言 LLM-facing schema 保持宽松（无复杂 union/enum）、禁止 checklist heading 回流、断言 registry 本身没有长出逻辑。大块输出工具不要逐个写 UI 逻辑；registry 单点附加共享 `renderResult`，折叠态摘要给人看，展开态完整 `content` 给人/模型对照。

工具原则：

- execute 直接调 engine 函数，不 spawn 子进程。
- 参数 schema 简洁。
- 返回 content 给模型，details 给 TUI/日志。
- mutating tool 统一附带 state snapshot。
- light 常见：`get_status`、少量领域事件工具；`patch_state` 只 debug。
- standard 常见：`code_act`、`get_status`、`lookup`，其中 `code_act` 暴露 domain API 而非 raw state。
- 注册清单整局稳定：不做运行时 toolset 切换，动态增删工具会毁掉 prompt cache。条件可用性写进 description 和错误。

## 测试

至少测：

- hydrate 从 session snapshot 恢复。
- reducer 对关键 domain event 产生预期 state：直接构造 draft 喂事件，不经过 store。
- public projection 不含任何 secret 字段。
- patch 拒绝非法 root / protected path。
- migration 把旧 fixture 升到当前 schema。
- mutating tool 会产生 snapshot。
- session compact 后有新锚点。

## 禁区

- 复制示例字段当 schema。
- 把 `state/state.json` 当真相源。
- 在运行时兼容多代旧字段。
- 让 GM 手写 migration patch。
- 标准方案再生成一堆独立 dice/combat/economy 字段 setter。
- 暴露常规玩法 `update_state` 万能工具。
