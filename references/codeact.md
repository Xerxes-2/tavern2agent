# CodeAct

标准方案默认用单个 `code_act` 工具 + 沙箱。GM 写一小段 JS，沙箱执行计算、随机、状态写入、查询，再把结构化结果交给 GM 叙事。

纯 prompt / light 不要套 CodeAct。

## 目的

CodeAct 解决多工具形态的三个问题：

- 多步结算要跨很多 tool call。
- LLM 容易忘顺序或心算错误。
- 状态扫描和时间压缩很难一轮完成。

CodeAct 不是让 LLM 在沙箱里写小说。沙箱只产机械结果和叙事钩子。

## 三层 API

```txt
scene(...)       高层活动：战斗、演出、探索、休息
组合函数         常用多字段联动：交易、发帖、推进时间、结算任务
原语函数         status、lookup、patch、adjust_*、log
```

规则：

- 原语层 + 组合层必须有。
- 场景层按题材决定；有“持续活动 + 结算 + 事件”就建。
- GM 优先用最高层；覆盖不到再降层。
- `patch` 只兜底，不能绕过有规则的组合函数。

## 沙箱契约

- 写函数返回结构化结果，如 `{ before, after }`、`{ settlement, events, hooks }`。
- 写函数自动 log 人类可读摘要。
- 查询未命中 throw，供脚本 try/catch。
- `status()` 返回 clone，不给 state 引用。
- 禁止 fs/process/require/import 等 host 出口。
- 设置超时，防死循环。
- 执行后 dirty state 走 session-backed state 链路。

## `.d.ts` 是 API 权威

为沙箱暴露函数写 `engine/codeact-sandbox.d.ts`。它同时服务：

- GM 每轮看到的函数签名。
- 沙箱实现的类型检查。
- 工具 description 的权威 API 段。

不要用长自然语言逐个解释函数。类型签名 + 少量 JSDoc 足够。

示意：

```ts
declare function status(): Readonly<WorldState>;
declare function log(message: string): void;
/** protected paths 会拒绝非法写入 */
declare function patch(ops: PatchOp[]): void;
/** 未命中则 throw */
declare function lookup(type: string, query: string): LookupEntry[];

declare function adjust_money(delta: number, reason?: string): Change<number>;
declare function advance(minutes: number, reason?: string): AdvanceResult;
declare function scene(type: string, params: unknown): SceneResult;
```

实际签名按卡片生成，不抄示例字段。

## protected paths

凡有规则的字段，禁止裸 `patch`：

- 金钱/资源
- 装备/背包
- 技能/属性点
- 任务/章节
- 好感/关系
- 场景/时间

这些必须走组合函数或 scene。`patch` 命中受保护路径时 throw，并提示正确函数。

## Prompt 要点

写进 GM 规则：

- 状态变化、掷骰、时间推进、经济/战斗/任务结算必须用 `code_act`。
- 时间跳跃用一段 scene/advance 序列，不拆成多轮。
- 脚本里只做机械层；叙事在工具返回后写。
- 不要 `log(scene(...))`；写函数会自动 log。
- 不调用 `code_act` 就不能声称状态已改变。

`code_act` description：

1. 必须调用场景。
2. 严禁行为。
3. 三层优先级：scene > 组合 > 原语。
4. 嵌入 `.d.ts`。

## 与底层 state 的关系

CodeAct 不自建存档系统。沙箱函数最终调用同一套 state 基建：

```txt
sandbox write → patchState / writeState → in-memory store → session custom entry → debug export
```

subagent 不拿 `code_act`。子代理只给文本/结构化建议；GM 决定是否写入状态。

## 校验

- [ ] 原语层 + 组合层存在。
- [ ] 有活动单元时 scene 层存在。
- [ ] 写函数返回结构化结果并自动 log。
- [ ] lookup 失败 throw。
- [ ] status 返回 clone。
- [ ] 沙箱有超时和 host 出口限制。
- [ ] protected paths 覆盖关键字段。
- [ ] description 嵌入 `.d.ts`。
- [ ] GM 规则写清三层优先级和禁区。
- [ ] 状态写入走 session-backed state。
- [ ] 下场测试中至少一次真实调用 `code_act`。
