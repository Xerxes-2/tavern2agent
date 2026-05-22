# TS 引擎模块参考

以下是 TypeScript 原生引擎的核心模块骨架。extensions 直接 import，工具零开销调用。

> **重要**：以下代码中的 `initialBlankState()`、`get_status` / `skill_check` 工具都是**通用示例骨架**，演示模式而非提供可照搬的 schema。转换其他卡片时，状态结构必须从卡片 MVU 条目（`[mvu_update]` / `[mvu_plot]`）的变量定义中动态提取——不要照搬示例字段名。

> **回退 / 存档不在本文档**。死亡回溯、章节存档、撤销上一轮交给 pi 平台层的回退扩展（`pi-rewind-hook` 等），见 SKILL.md §六。本文档只讲状态写入。

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
```

轻量方案注册 `get_status` / `patch_state` 两个工具；标准方案在此基础上注册 engine 模块工具（dice、combat 等）。

### 跨回退持久的「永久记忆」（可选，仅死亡循环类机制需要）

需要"玩家在死亡/周目切换后保留某些记忆"时，加一份**不被回退扩展 snapshot** 的持久层。方法是把它写到 gitignored 路径——`pi-rewind-hook` 等扩展会跳过 gitignored 文件，刚好绕过整体回退。

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

只用于人工查 bug；不用于回退（回退走 pi-rewind-hook）。原事件溯源 + `dispatch()/rollback()/setCheckpoint()` 设计已删除——chat 与 state 解耦让自建回滚做不干净，统一外包给平台层扩展更可靠。

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
