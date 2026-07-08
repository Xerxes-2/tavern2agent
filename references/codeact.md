# CodeAct 执行载体

CodeAct 是四层 API 的一种执行方式：单个 `code_act` 工具承载 typed command layer。GM 写受限 JS，沙箱执行计算、随机、状态写入、查询，再把结构化结果交给 GM 叙事。typed tools 与 CodeAct 的取舍见 `references/tool-abstraction.md` 的「选择取舍」；四层 API 与 protected paths 同样适用于 CodeAct。

light 档不要套 CodeAct。沙箱只产机械结果、结算摘要和叙事钩子；禁止在沙箱里写小说正文，禁止当自由脚本入口。

## 适用点

- 多步结算要跨很多 tool call。
- LLM 容易忘顺序或心算错误。
- 状态扫描、条件分支、批量结算和时间压缩很难一轮完成。

看到 prompt 里出现「先 A，再 B，再 C，最后 D」时，优先考虑把这个工作流做成 CodeAct API 或深 typed tool，而不要继续加自然语言纪律。

## 沙箱契约

沙箱用 `node:vm`（`vm.createContext` + `vm.Script.runInContext`），不是 `child_process`、`eval` 或 Docker。

- 写函数返回结构化结果，如 `{ before, after }`、`{ settlement, events, hooks }`。
- 写函数自动 log 人类可读摘要。
- 查询未命中 throw，供脚本 try/catch。
- `status()` 返回 clone，不给 state 引用。
- 禁止 fs/process/require/import 等 host 出口。
- 设置超时，防死循环。
- 执行后 dirty state 走 session-backed state 链路。
- 脚本中只做机械层；不要生成小说正文。

## `.d.ts` 是 API 权威

为沙箱暴露函数写 `engine/codeact-sandbox.d.ts`。它同时服务：

- GM 每轮看到的函数签名。
- 沙箱实现的类型检查。
- 工具 description 的权威 API 段。

示意：

```ts
declare function status(): Readonly<WorldState>;
declare function log(message: string): void;
declare function lookup(type: string, query: string): LookupEntry[];

declare function commitTurn(input: TurnCommitInput): TurnCommitResult;
declare function startSceneBeat(input: StartSceneBeatInput): SceneBeatResult;
declare function finishCurrentBeat(input: FinishCurrentBeatInput): SceneBeatResult;
declare function completeObjective(summaryOrId: string): ObjectiveResult;
declare function adjustMoney(input: { ownerActorId: string; amount: number; reason?: string }): Change<number>;

/** debug-only；protected paths 会拒绝非法写入 */
declare function patch(ops: PatchOp[], reason: string): void;
```

实际签名按卡片生成，不抄示例字段。

## 与底层 state 的关系

CodeAct 不自建存档系统。沙箱函数最终调用同一套 state 基建：

```txt
sandbox write → engine/domain functions → in-memory store → session custom entry → debug export
```

subagent 不拿 `code_act`。子代理只给文本/结构化建议；状态写入仍由 GM 走主 engine。

## CodeAct 校验

本清单是 CodeAct 实现阶段闸门；完工闸门见 `references/validation.md`。

- [ ] `code_act` description 嵌入 `.d.ts`。
- [ ] 沙箱有超时和 host 出口限制。
- [ ] status 返回 clone。
- [ ] lookup 失败 throw。
- [ ] 写函数返回结构化结果并自动 log。
- [ ] 状态写入走 session-backed state。
- [ ] 下场测试中至少一次真实调用 `code_act`，且脚本使用 scene/组合 API，不只裸 patch。
