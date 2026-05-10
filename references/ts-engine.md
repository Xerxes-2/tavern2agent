# TS 引擎模块参考

以下是 TypeScript 原生引擎的核心模块骨架。extensions 直接 import，工具零开销调用。

> **重要**：以下代码中的 `initialBlankState()` 和部分事件处理器以 Re:0 为例，包含 `魔女残香`、`死亡回溯计数`、`chapter.is_changed_chapter` 等 Re:0 特有字段。转换其他卡片时，状态结构必须从卡片 MVU 条目的变量定义中动态提取——不要照搬此处的字段。

## 状态引擎 (state.ts)

```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const STATE_DIR = join(process.cwd(), ".pi/extensions/re0/state");
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
      const dc = (deepGet(state, "主角.死亡回溯计数") as number) || 0;
      const scent = (deepGet(state, "主角.魔女残香") as number) || 0;
      deepSet(state, "主角.死亡回溯计数", dc + 1);
      deepSet(state, "主角.魔女残香", scent + 1);
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

// ── 事件构造器 ──
export const evt = {
  set: (path: string, value: unknown) => ({ type: "set", path, value }),
  delta: (path: string, value: number) => ({ type: "delta", path, value }),
  deathRewind: () => ({ type: "death_rewind", path: "", value: null }),
  // ... 更多事件类型按需添加
};

// ⚠️ 以下初始状态以 Re:0 为例。转换其他卡片时，
// 必须从 MVU 条目（[mvu_update] 和 [mvu_plot]）的变量定义中提取 schema 动态生成。
// 详见 SKILL.md「分析阶段：第二步」中的提取规则。
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
      死亡回溯计数: 0,    // Re:0 特有
      魔女残香: 0,          // Re:0 特有
    },
    关系列表: {},
    敌人列表: {},
    任务列表: {},
    时间: { 年月日: "", 时间: "" },
    chapter: { is_changed_chapter: "NO" },  // Re:0 特有
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

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { getCurrentState, dispatch, evt } from "../engine/state";
import { check, calcDamage } from "../engine/dice";

export function registerAllTools(pi: ExtensionAPI) {
  // 查询工具
  pi.registerTool({
    name: "re0_status",
    label: "角色状态",
    description: "查看主角完整面板",
    promptSnippet: "查询主角当前的生命值、魔法值、属性、装备和技能",
    parameters: Type.Object({}),
    async execute() {
      const s = getCurrentState();
      const p = s.主角 as Record<string, unknown>;
      return {
        content: [{ type: "text", text: JSON.stringify(p, null, 2) }],
        details: {},
      };
    },
  });

  // 行动工具
  pi.registerTool({
    name: "re0_skill_check",
    label: "属性检定",
    description: "进行属性检定，掷骰判定成功/失败",
    promptSnippet: "掷骰进行属性检定",
    parameters: Type.Object({
      attribute: Type.String({ description: "属性名" }),
      difficulty: Type.Optional(Type.String({ description: "难度：简单/普通/困难/极难/噩梦" })),
    }),
    async execute(_id, params) {
      const s = getCurrentState();
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
4. **state 目录放在 extension 内部**——`.pi/extensions/re0/state/`，不污染项目根目录
5. **系统 prompt 每次注入当前状态**——agent 始终知道最新游戏局面
