# TS 引擎模块参考

以下是 TypeScript 原生引擎的核心模块骨架。extensions 直接 import，工具零开销调用。

> **重要**：以下代码中的 `initialBlankState()`、`get_status` / `skill_check` 工具都是**通用示例骨架**，演示模式而非提供可照搬的 schema。转换其他卡片时，状态结构必须从卡片 MVU 条目（`[mvu_update]` / `[mvu_plot]`）的变量定义中动态提取——不要照搬示例字段名。

> **状态持久化原则**：轻量/标准方案从一开始使用 session-backed state。pi session custom entry 是真相源；`state/` 只做 debug export / legacy fallback。死亡回溯、章节存档、撤销上一轮不在 engine 内做事件溯源，按 pi session tree/fork 的分支语义恢复对应状态快照，见 SKILL.md §六。

## 状态引擎 (state.ts)

凡落到轻量/标准方案、需要持久 state 的卡，都建议把状态层当成“宪法”设计：

- `INITIAL_STATE` + schema 是唯一当前结构。
- 运行时只支持当前 schema；旧字段只在 migration 中读取。
- `patch_state` 做 strict path 保护：已有专用工具负责的字段禁止裸 patch。
- 派生值运行时计算，不写回 state（例如总攻击、HP 上限、资源上限）。
- 状态迁移用显式 `migrate_state` 工具触发，不让 GM 自由手写迁移 patch。

这能显著降低 vibe coding 项目的长期腐化：不要为兼容临时在运行时到处加 fallback。完整迁移与测试模式见 `references/state-schema-migrations.md`。


> **建议流程（标准方案）**：写 `state.ts` 之前，先单独输出 state schema + engine 操作清单给用户 review，再动手。schema 必须覆盖用户卡创建字段；详见 SKILL.md §四「中间检查点」+ `mvu-mapping.md` 两条 ⚠️ 块。

### 轻量 / 标准方案

**状态更新仍使用 JSON Patch（RFC 6902）**：`patch_state` 工具只传变化字段路径，不传整个 state。省 token 且防 LLM 覆盖无关字段。

但持久化不要以 `state/state.json` 为真相源。推荐骨架：

```txt
pi session custom entry (<card-slug>-state)  ← 真相源，跟随 session 分支
        ↓ hydrate/export
in-memory state + globalThis store           ← 工具和 hooks 读写
        ↓ debug export
state/state.json                             ← 人工查看 / 旧存档导入 fallback
```

依赖 `rfc6902`：

```bash
npm install rfc6902
```

`engine/core/state.ts` 只负责状态读写、patch、session snapshot 结构；具体 schema 字段由卡片 MVU/InitVar 提取：

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { applyPatch } from "rfc6902";
import { INITIAL_STATE } from "./initial-state";

export const STATE_SESSION_ENTRY_TYPE = "<card-slug>-state";
export const STATE_SESSION_VERSION = 1;

export interface SessionStateSnapshot {
  v: typeof STATE_SESSION_VERSION;
  turn: number;
  state: Record<string, unknown>;
}

const STATE_FILE = join(process.cwd(), "state", "state.json");
const TURN_FILE = join(process.cwd(), "state", ".turn");
const STORE_KEY = "__<card_slug>_state_store__";

type Store = { currentState: Record<string, unknown> | null; turn: number; dirty: boolean; unavailable?: string | null };

function store(): Store {
  const g = globalThis as Record<string, unknown>;
  return (g[STORE_KEY] as Store) ?? (g[STORE_KEY] = { currentState: null, turn: 0, dirty: false }) as Store;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function exportDebugState(state: Record<string, unknown>, turn: number) {
  mkdirSync(dirname(STATE_FILE), { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  writeFileSync(TURN_FILE, String(turn));
}

function installState(state: Record<string, unknown>, turn = 0, dirty = false) {
  const s = store();
  s.currentState = clone(state);
  s.turn = Math.max(0, Math.floor(turn) || 0);
  s.dirty = dirty;
  s.unavailable = null;
  exportDebugState(s.currentState, s.turn);
}

function readLegacyDebugState(): Record<string, unknown> | null {
  if (!existsSync(STATE_FILE)) return null;
  return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
}

function readLegacyDebugTurn(): number {
  if (!existsSync(TURN_FILE)) return 0;
  return Number(readFileSync(TURN_FILE, "utf-8").trim()) || 0;
}

export function hydrateStateFromSessionBranch(
  entries: unknown[],
  options: { allowFileFallback?: boolean; allowInitialFallback?: boolean } = {},
) {
  for (let i = entries.length - 1; i >= 0; i--) {
    const entry = entries[i] as any;
    const snapshot =
      entry?.type === "custom" && entry?.customType === STATE_SESSION_ENTRY_TYPE ? entry.data :
      entry?.message?.role === "toolResult" ? entry.message.details?.[STATE_SESSION_ENTRY_TYPE] :
      null;

    if (snapshot?.v === STATE_SESSION_VERSION && snapshot.state) {
      installState(snapshot.state, snapshot.turn, false);
      return { source: "session" as const, turn: store().turn };
    }
  }

  if (options.allowFileFallback) {
    const fileState = readLegacyDebugState();
    if (fileState) {
      installState(fileState, readLegacyDebugTurn(), false);
      return { source: "file" as const, turn: store().turn };
    }
  }

  if (options.allowInitialFallback) {
    installState(INITIAL_STATE, 0, true);
    return { source: "initial" as const, turn: store().turn };
  }

  const s = store();
  s.currentState = null;
  s.dirty = false;
  s.unavailable = "当前 session 分支没有状态快照；拒绝自动写入 INITIAL_STATE 以免污染存档。";
  return { source: "unavailable" as const, turn: s.turn, reason: s.unavailable };
}

function ensureHydrated() {
  const s = store();
  if (s.unavailable) throw new Error(s.unavailable);
  if (s.currentState) return;
  const fileState = readLegacyDebugState();
  if (fileState) installState(fileState, readLegacyDebugTurn(), false);
  else installState(INITIAL_STATE, 0, true);
}

export function getState(): Record<string, unknown> {
  ensureHydrated();
  return clone(store().currentState!);
}

export function writeState(state: Record<string, unknown>) {
  const s = store();
  installState(state, s.turn, true);
}

export function patchState(ops: Array<{ op: string; path: string; value?: unknown }>) {
  const state = getState();
  const raw = state as Record<string, unknown>;
  // rfc6902 不自动创建中间对象：这里按项目需要预创建并做 strict path 校验。
  applyPatch(raw, ops as any);
  writeState(state);
}

export function getStateSnapshot(): SessionStateSnapshot {
  ensureHydrated();
  const s = store();
  return { v: STATE_SESSION_VERSION, turn: s.turn, state: clone(s.currentState!) };
}

export function isStateDirty(): boolean {
  return Boolean(store().dirty && !store().unavailable);
}

export function markStatePersisted() {
  store().dirty = false;
}

export function incrementTurnCount(): number {
  const s = store();
  if (s.unavailable) return s.turn;
  s.turn += 1;
  s.dirty = true;
  if (s.currentState) exportDebugState(s.currentState, s.turn);
  return s.turn;
}
```

`tools/registry.ts` 建议统一包装 mutating tools：

```typescript
import { STATE_SESSION_ENTRY_TYPE, getStateSnapshot, isStateDirty, markStatePersisted } from "../engine/core/state";

function attachStateSnapshot(def: any) {
  if (typeof def.execute !== "function") return def;
  const execute = def.execute;
  return {
    ...def,
    async execute(...args: any[]) {
      const result = await execute(...args);
      if (result && typeof result === "object" && isStateDirty()) {
        result.details = { ...(result.details || {}), [STATE_SESSION_ENTRY_TYPE]: getStateSnapshot() };
        markStatePersisted();
      }
      return result;
    },
  };
}
```

`extension.ts` 负责 hydrate 和兜底 append：

```typescript
pi.on("session_start", async (_event, ctx) => {
  const branch = ctx.sessionManager.getBranch();
  hydrateStateFromSessionBranch(branch, {
    allowFileFallback: true,          // 仅用于旧文件存档首次导入
    allowInitialFallback: branch.length === 0,
  });
});

pi.on("session_tree", async (_event, ctx) => {
  hydrateStateFromSessionBranch(ctx.sessionManager.getBranch(), {
    allowFileFallback: false,
    allowInitialFallback: false,
  });
});

pi.on("before_agent_start", async (event) => {
  incrementTurnCount();
  return { systemPrompt: event.systemPrompt };
});

pi.on("turn_start", async () => {
  if (!isStateDirty()) return;
  pi.appendEntry(STATE_SESSION_ENTRY_TYPE, getStateSnapshot());
  markStatePersisted();
});

pi.on("agent_end", async () => {
  if (!isStateDirty()) return;
  pi.appendEntry(STATE_SESSION_ENTRY_TYPE, getStateSnapshot());
  markStatePersisted();
});
```

轻量方案注册 `get_status` / `patch_state` 两个工具；标准方案在此基础上注册 engine 模块工具（dice、combat 等）。

### 跨回退持久的「永久记忆」（可选，仅死亡循环类机制需要）

需要“玩家在死亡/周目切换后保留某些记忆”时，加一份**不随 session 分支读档回退**的持久层。方法是把它写到 `meta/persistent.json`（gitignored，不发布），或写入独立 permanent custom entry 类型。

```typescript
const META_DIR = process.env.TAVERN2AGENT_META_DIR ?? "meta";  // 加进 .gitignore
const PERSISTENT_FILE = join(META_DIR, "persistent.json");

export function getPersistent(): Record<string, unknown> {
  if (!existsSync(PERSISTENT_FILE)) return {};
  return JSON.parse(readFileSync(PERSISTENT_FILE, "utf-8"));
}

export function setPersistent(key: string, value: unknown) {
  const cur = getPersistent();
  cur[key] = value;
  mkdirSync(dirname(PERSISTENT_FILE), { recursive: true });
  writeFileSync(PERSISTENT_FILE, JSON.stringify(cur, null, 2));
}
```

注册 `get_persistent` / `set_persistent` 工具供 GM 在死亡或周目切换时写入"记忆"标记。无此类机制的卡跳过——绝大多数卡用不到。

### 历史日志（可选，仅审计/调试需要）

如需追溯「上一轮 GM 改了哪些字段」，在 `patchState` 里 append 一条 JSONL：

```typescript
const LOG_FILE = join(STATE_DIR, "patches.jsonl");
// 在 applyPatch 之前/之后写入：
appendFileSync(LOG_FILE, JSON.stringify({ ts: Date.now(), ops }) + "\n");
```

只用于人工查 bug；不用于读档。原事件溯源 + `dispatch()/rollback()/setCheckpoint()` 设计已删除——chat 与 state 解耦让自建回滚做不干净，统一按 pi session 分支恢复快照。

## 注意力调度 (attention.ts)

LLM 不擅长计数和定时触发。标准方案存在「每 N 轮调用同伴」「战斗后必须 try_level_up」「NPC 互动后必更新好感度」「DLC 启用后定期提醒」任一需求时，写本模块。

回合数自行维护：在 `state.ts` 给 state 加一个 `meta.turn` 计数器（每次 `patchState` 或 `before_agent_start` 自增 1），跨进程持久靠 state.json 本身。

```typescript
// engine/attention.ts
export function buildReminders(): AttentionReminder[] {
  const reminders: AttentionReminder[] = [];
  const state = getState();
  const turn = ((state.meta as Record<string, unknown>)?.turn as number) ?? 0;

  // 每 4 轮提醒同伴
  if (companionEnabled && turn % 4 === 0) {
    reminders.push({ level: "info", message: "同伴已静默 N 轮，可以调用 subagent" });
  }
  // XP 溢出 — 每轮检查
  if (xp >= required) {
    reminders.push({ level: "critical", message: "⚠️ 经验溢出，必须调用 try_level_up" });
  }
  return reminders;
}
```

**注入点**：`extension.ts` 的 `before_agent_start` 中调用 `buildReminders()`，用 `## ⚠️ 系统提醒` 格式追加到 system prompt 末尾。

**双重保障原则**：系统级注入（`attention.ts`）+ 工具级 `promptGuidelines`（写死 ⚠️ 前缀），两层都失效才遗漏。

## 骰子引擎 (dice.ts)

```typescript
export function attrMod(value: number): number {
  return Math.floor((value - 10) / 2);
}

interface CheckResult {
  success: boolean;
  level: string;
  roll: number;
  mod: number;
  total: number;
  dc: number;
  description: string;
}

export function check(attrValue: number, targetDC: number, bonus = 0): CheckResult {
  const roll = Math.floor(Math.random() * 6) + 1;
  const mod = attrMod(attrValue);
  const total = roll + mod + bonus;
  const diff = total - targetDC;

  let level: string, description: string;
  if (diff >= 10) { level = "大成功"; description = "完美达成"; }
  else if (diff >= 5) { level = "成功"; description = "顺利达成"; }
  else if (diff >= 0) { level = "勉强成功"; description = "达成但有代价"; }
  else if (diff >= -5) { level = "失败"; description = "未达成"; }
  else { level = "大失败"; description = "惨败"; }

  return { success: diff >= 0, level, roll, mod, total, dc: targetDC, description };
}

export function calcDamage(
  hitResult: CheckResult,
  attackerStr: number,
  weaponAtk = 0,
  defenderArmor = 0,
  defenderEndurance = 0
) {
  if (!hitResult.success) return { damage: 0, absorbed: 0, net: 0, description: "未命中" };

  let base = hitResult.roll + attrMod(attackerStr) + weaponAtk;
  if (hitResult.level === "大成功") base = Math.floor(base * 1.5);

  const absorbed = Math.min(defenderArmor, base);
  const net = Math.max(0, base - absorbed);
  const endReduction = Math.max(0, attrMod(defenderEndurance));
  const final = Math.max(1, net - endReduction);

  return { damage: base, absorbed, enduranceReduction: endReduction, net: final,
    description: `造成 ${final} 点伤害` };
}
```

## 工具注册模式 (tools/registry.ts)

> **`tools/registry.ts` 是工具实现的唯一聚集地**。`extension.ts` 只调用 `registerAllTools(pi)`，不要在 extension 里内联工具——否则 registry.ts 沦为死代码。extension 入口契约见 `references/pi-integration.md`。


```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Container, Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { getState, patchState, deepGet } from "../engine/state";
import { check, calcDamage } from "../engine/dice";

export function registerAllTools(pi: ExtensionAPI) {
  // ── 状态查询 ──
  pi.registerTool({
    name: "get_status",  // 工具名按本卡主题命名
    label: "角色状态",
    description: "查看主角完整面板",
    promptSnippet: "查询主角当前的生命值、魔法值、属性、装备和技能",
    parameters: Type.Object({}),
    async execute() {
      const s = getState();
      const p = s.主角 as Record<string, unknown>;
      return {
        content: [{ type: "text", text: JSON.stringify(p, null, 2) }],
        details: {},
      };
    },
  });

  // ── 状态写入（JSON Patch）──
  pi.registerTool({
    name: "patch_state",
    label: "Patch State",
    description: "用 JSON Patch (RFC 6902) 更新游戏状态。只传变化字段的路径和值，不需要传整个 state。",
    promptSnippet: "用 JSON Patch 更新游戏状态，只传要改的字段",
    promptGuidelines: [
      "使用 patch_state 更新状态，每次只传要修改的字段路径。不需要传整个 state 对象。",
      "patch_state 的 path 是 / 分隔的 JSON Pointer，如 /主角/生命值/当前值",
      "op 可选: replace（修改）、add（新增/替换）、remove（删除）",
    ],
    parameters: Type.Object({
      ops: Type.Array(Type.Object({
        op: Type.Union([Type.Literal("add"), Type.Literal("replace"), Type.Literal("remove")]),
        path: Type.String({ description: "JSON Pointer 路径，如 /主角/生命值/当前值" }),
        value: Type.Optional(Type.Unknown()),
      })),
    }),
    async execute(_id, params) {
      const before = getState();
      patchState(params.ops);
      const after = getState();
      // 每行一条变化摘要，给 LLM 和玩家都能读懂
      const changes = params.ops.map(op => {
        const label = op.path.split("/").filter(Boolean).join("→");
        const oldVal = deepGet(before, op.path.slice(1).replace(/\//g, "."));
        if (op.op === "remove") return `- ${label}（已移除）`;
        return `${label}: ${oldVal} → ${op.value}`;
      });
      return {
        content: [{ type: "text", text: changes.join("\n") }],
        details: params.ops,
      };
    },
    renderResult(result, { expanded }, theme) {
      const text = result.content[0];
      if (!text || text.type !== "text") return new Container();
      const lines = text.text.split("\n");
      if (!expanded && lines.length > 3) {
        return new Text(
          lines.slice(0, 3).map(l => theme.fg("muted", l)).join("\n") +
            "\n" + theme.fg("dim", `... 共 ${lines.length} 项`),
          0, 0,
        );
      }
      return new Text(lines.map(l => theme.fg("muted", l)).join("\n"), 0, 0);
    },
  });

  // ── 行动工具 ──
  pi.registerTool({
    name: "skill_check",
    label: "属性检定",
    description: "进行属性检定，掷骰判定成功/失败",
    promptSnippet: "掷骰进行属性检定",
    parameters: Type.Object({
      attribute: Type.String({ description: "属性名" }),
      difficulty: Type.Optional(Type.String({ description: "难度：简单/普通/困难/极难/噩梦" })),
    }),
    async execute(_id, params) {
      const s = getState();
      const attrs = (s.主角 as Record<string, unknown>).属性列表 as Record<string, number>;
      const dcMap: Record<string, number> = { 简单: 8, 普通: 12, 困难: 16, 极难: 20, 噩梦: 25 };
      const dc = dcMap[params.difficulty || "普通"] || 12;
      const attrVal = attrs[params.attribute] || 10;
      const result = check(attrVal, dc);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: {},
      };
    },
  });

  // ... 其他工具
}
```

## 关键要点

1. **state.ts 是核心**——所有引擎模块依赖它，所有工具通过它读写
2. **工具 execute 直接调引擎函数**——不需要 spawn 子进程
3. **TypeBox 做参数校验**——pi 自带，不需要额外安装
4. **state 目录由 extension 决定**——通过 `TAVERN2AGENT_STATE_DIR` 注入。pi extension 一般放 `.pi/extensions/<name>/state/`；独立运行默认 `state/`
5. **系统 prompt 每次注入当前状态**——agent 始终知道最新游戏局面
