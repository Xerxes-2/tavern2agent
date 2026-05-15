# TS 引擎模块参考

以下是 TypeScript 原生引擎的核心模块骨架。extensions 直接 import，工具零开销调用。

> **重要**：以下代码中的 `initialBlankState()`、`death_rewind` 事件处理器、`get_status` / `skill_check` 工具都是**通用示例骨架**，演示模式而非提供可照搬的 schema。转换其他卡片时，状态结构必须从卡片 MVU 条目（`[mvu_update]` / `[mvu_plot]`）的变量定义中动态提取，事件类型也按本卡机制设计——不要照搬示例字段名。

## 状态引擎 (state.ts)

> **建议流程（中等+ 方案）**：写 `state.ts` 之前，先单独输出一份 state schema（TS interface 或 JSON 示例）+ 事件/操作清单（完整方案：事件名 + payload；中等方案：操作清单），跟用户对齐再动手。MVU 模型误读是后期返工成本最高的环节，前置确认比写完再改便宜得多。轻量方案 schema 通常一眼能看完，可跳过。

### 轻量 / 中等方案

适用于键值状态或整轮回滚场景（不需要事件溯源）。

**状态更新使用 JSON Patch（RFC 6902）**：`patch_state` 工具只传变化字段路径，不传整个 state。省 token 且防 LLM 覆盖无关字段。

依赖 `rfc6902`（同时提供 `applyPatch` + `createPatch` 做 diff）：

```bash
npm install rfc6902
```

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { applyPatch } from "rfc6902";

const STATE_DIR = process.env.TAVERN2AGENT_STATE_DIR ?? "state";
const STATE_FILE = join(STATE_DIR, "state.json");
const INITIAL_STATE: Record<string, unknown> = { /* 从 initvar 或 MVU 条目提取 */ };

export function getState(): Record<string, unknown> {
  if (!existsSync(STATE_FILE)) {
    mkdirSync(dirname(STATE_FILE), { recursive: true });
    writeFileSync(STATE_FILE, JSON.stringify(INITIAL_STATE, null, 2));
    return { ...INITIAL_STATE };
  }
  return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
}

export function writeState(state: Record<string, unknown>) {
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

/** JSON Patch (RFC 6902) — 递归创建缺失中间对象后原地修改 state */
export function patchState(ops: Array<{ op: string; path: string; value?: unknown }>) {
  const state = getState();
  // rfc6902 不自动创建中间对象 — 预处理：逐段 ensure 路径存在
  const raw = state as unknown as Record<string, unknown>;
  for (const op of ops) {
    if (op.op === "remove") continue;
    const segments = op.path.split("/").filter(Boolean);
    if (segments.length <= 1) continue; // 顶层 key 不需要预创建
    let cur: Record<string, unknown> = raw;
    for (let i = 0; i < segments.length - 1; i++) {
      const key = segments[i];
      if (!(key in cur) || typeof cur[key] !== "object" || cur[key] === null) {
        cur[key] = {};
      }
      cur = cur[key] as Record<string, unknown>;
    }
  }
  applyPatch(raw, ops);
  writeState(state);
}

/** 按 dot-separated 路径读嵌套值，如 deepGet(state, "主角.生命值.当前值") */
export function deepGet(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const k of keys) {
    if (current && typeof current === "object" && k in (current as any)) {
      current = (current as Record<string, unknown>)[k];
    } else return undefined;
  }
  return current;
}

// — 仅中等方案需要以下 —
const SNAP_DIR = join(STATE_DIR, "snapshots");

export function snapshotBeforeTurn(turnId: string) {
  if (!existsSync(STATE_FILE)) return;
  mkdirSync(SNAP_DIR, { recursive: true });
  copyFileSync(STATE_FILE, join(SNAP_DIR, `${turnId}.json`));
}

export function rollbackToTurn(turnId: string) {
  const snap = join(SNAP_DIR, `${turnId}.json`);
  if (!existsSync(snap)) throw new Error(`无快照: ${turnId}`);
  copyFileSync(snap, STATE_FILE);
}
```

胶水层挂钩（每轮开始前）：
- pi：`before_agent_start` 事件没有 `turnId` 字段；用 `event.prompt` 的前 20 字符 + `Date.now()` 做简易 ID，或自行维护递增计数器

轻量方案注册 `get_status` / `patch_state` 两个工具；中等方案在此基础上注册 engine 模块工具。

### 中等方案：重 roll / 回滚（粗粒度）

agent 删不掉自己已发出的 chat turn，不支持单条 swipe。只做粗粒度：扔掉整段 chat、回退 state 到指定 snapshot，重开会话。

在 `state.ts` 末尾加：

```typescript
export function markResume(turnId: string) {
  rollbackToTurn(turnId);
  writeFileSync(join(STATE_DIR, "resume-to.txt"), turnId);
}
```

注册 `request_rollback(turnId)` 工具。流程：
1. 用户说「回到第 5 轮重新开始」
2. agent 调 `request_rollback("5")` → state 回滚 + 写入 `resume-to.txt`
3. agent 提示用户关掉重开
4. 启动 hook 检测 `resume-to.txt`，把 state 内容 +「你回到了第 5 轮开始」前置到第一条用户消息，然后删除 marker

chat 全清，state 干净。需要保留对白的细粒度 reroll 必须靠平台原生删消息 API，pi 若有就用。

### 完整方案（事件溯源）

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

// 跨平台契约：胶水层通过 TAVERN2AGENT_STATE_DIR 注入。
// pi extension 通常设为 `.pi/extensions/<name>/state`；
// 独立运行默认落到项目根的 `state/`。
const STATE_DIR = process.env.TAVERN2AGENT_STATE_DIR ?? join(process.cwd(), "state");
const EVENTS_FILE = join(STATE_DIR, "events", "events.jsonl");
const INDEX_FILE = join(STATE_DIR, "index.json");

interface Event {
  id: number;
  type: string;
  path: string;
  value: unknown;
  oldValue?: unknown;
  timestamp: number;
}

interface Index {
  head: number;
  eventCount: number;
  checkpoint: { event_id: number; 年月日: string; 时间: string } | null;
}

// ── 文件管理 ──
function ensureFiles() {
  mkdirSync(join(STATE_DIR, "events"), { recursive: true });
  if (!existsSync(INDEX_FILE)) {
    writeFileSync(INDEX_FILE, JSON.stringify({ head: 0, eventCount: 0, checkpoint: null }));
  }
}

function readIndex(): Index {
  return JSON.parse(readFileSync(INDEX_FILE, "utf-8"));
}

function writeIndex(idx: Index) {
  writeFileSync(INDEX_FILE, JSON.stringify(idx, null, 2));
}

// ── 事件日志 ──
function readAllEvents(): Event[] {
  if (!existsSync(EVENTS_FILE)) return [];
  const raw = readFileSync(EVENTS_FILE, "utf-8").trim();
  if (!raw) return [];
  return raw.split("\n").map(line => JSON.parse(line));
}

function appendEvent(event: Omit<Event, "id" | "timestamp">): number {
  const idx = readIndex();
  const id = idx.eventCount + 1;
  const full: Event = { ...event, id, timestamp: Date.now() };
  writeFileSync(EVENTS_FILE, JSON.stringify(full) + "\n", { flag: "a" });
  idx.head = id;
  idx.eventCount = id;
  writeIndex(idx);
  return id;
}

// ── 状态计算 ──
function deepGet(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const k of keys) {
    if (current && typeof current === "object" && k in current) {
      current = (current as Record<string, unknown>)[k];
    } else return undefined;
  }
  return current;
}

function deepSet(obj: Record<string, unknown>, path: string, value: unknown) {
  const keys = path.split(".");
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i];
    if (!(k in current) || typeof current[k] !== "object") {
      current[k] = {};
    }
    current = current[k] as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
}

function applyEvent(state: Record<string, unknown>, evt: Event) {
  const { type, path, value } = evt;
  if (!path && type !== "death_rewind" && type !== "remove_tasks") return;

  switch (type) {
    case "set":
      deepSet(state, path, value);
      break;
    case "delta": {
      const current = deepGet(state, path);
      if (typeof current === "number" && typeof value === "number") {
        deepSet(state, path, current + value);
      }
      break;
    }
    case "death_rewind": {
      // 演示：死亡回溯类机制把多个字段一并更新，事件溯源天然支持
      const count = (deepGet(state, "主角.回溯次数") as number) || 0;
      deepSet(state, "主角.回溯次数", count + 1);
      break;
    }
    // ... 其他事件类型按需添加
  }
}

// ── 公共 API ──
export function getCurrentState(): Record<string, unknown> {
  ensureFiles();
  const idx = readIndex();
  const events = readAllEvents().filter(e => e.id <= idx.head);
  const state = initialBlankState();  // ← 替换为卡片专属的初始状态
  for (const evt of events) applyEvent(state, evt);
  return state;
}

export function dispatch(event: Omit<Event, "id" | "timestamp">): number {
  ensureFiles();
  return appendEvent(event);
}

export function rollback(toEventId: number): Record<string, unknown> {
  ensureFiles();
  const idx = readIndex();
  const allEvents = readAllEvents();
  const kept = allEvents.filter(e => e.id <= toEventId);
  writeFileSync(EVENTS_FILE, kept.map(e => JSON.stringify(e)).join("\n") + "\n");
  idx.head = toEventId;
  idx.eventCount = toEventId;
  writeIndex(idx);
  return getCurrentState();
}

export function setCheckpoint(date: string, time: string) {
  const idx = readIndex();
  idx.checkpoint = { event_id: idx.head, 年月日: date, 时间: time };
  writeIndex(idx);
}

export function getCheckpoint() {
  return readIndex().checkpoint;
}

// ⚠️ 以下是通用骨架示例。转换具体卡片时，
// 必须从 MVU 条目（[mvu_update] 和 [mvu_plot]）的变量定义中提取 schema 动态生成。
// 详见 SKILL.md「卡片分析」中的提取规则。
function initialBlankState() {
  return {
    主角: {
      姓名: "{{user}}",
      种族: "人类",
      生命值: { 当前值: 10, 最大值: 10 },
      魔法值: { 当前值: 0, 最大值: 0 },
      体力值: { 当前值: 10, 最大值: 10 },
      护甲值: { 当前值: 0, 最大值: 0 },
      属性列表: { 力量: 10, 敏捷: 10, 智力: 10, 耐力: 10, 精神: 10, 魅力: 10 },
      物品列表: {},
      装备栏: {},
      技能列表: {},
    },
    关系列表: {},
    敌人列表: {},
    任务列表: {},
    时间: { 年月日: "", 时间: "" },
  };
}
```

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

> **`tools/registry.ts` 是工具实现的唯一聚集地**。`extension.ts` 只调用 `registerAllTools(pi)`，不要在 extension 里内联工具——否则 registry.ts 沦为死代码。extension 入口契约见 `references/platform-adapters.md`。


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
4. **state 目录由胶水层决定**——通过 `TAVERN2AGENT_STATE_DIR` 注入。pi extension 一般放 `.pi/extensions/<name>/state/`；独立运行默认 `state/`
5. **系统 prompt 每次注入当前状态**——agent 始终知道最新游戏局面
