# State Schema 防腐与存档迁移

复杂互动卡最容易腐化的不是 prompt，而是 state：字段名越长越多，模型越可能随手加错路径；为了兼容旧存档到处写 fallback，几轮之后运行时就没人知道哪份结构才是权威。

经验结论：**state schema 是宪法；旧存档只通过显式 migration 进入当前 schema；运行时不保留旧字段 fallback。**

## 一、schema 防腐原则

### 1. 当前 schema 唯一权威

- `INITIAL_STATE`、TypeBox/JSON schema、状态排序、派生逻辑必须描述同一套结构。
- 运行时只读当前字段。
- 旧字段名、旧对象形状、旧数组形状只允许出现在 migration 文件中。

不要在运行时写：

```typescript
const core = state.核心系统 ?? state.旧同伴 ?? state.companion;
```

应该写：

```typescript
const core = state.核心系统;
```

如果旧存档有 `/旧同伴`，在 migration 中一次性迁到当前字段 `/核心系统`。

### 2. 顶层 root 白名单

`patch_state`/`patchState` 必须拒绝未知顶层 key，防止模型污染：

```txt
/player
/user
/玩家
/角色
/旧同伴
```

这类错路径不能被静默创建。允许动态扩展的内容放在已知 root 下面，例如：

```txt
/主角/背包/<stableItemKey>
/关系/<npcId>
/任务/<questId>
/战斗/NPC/<npcId>
```

### 3. 专用工具字段禁止裸 patch

凡有专用工具管理的字段，`patch_state` 应硬拦，避免绕过规则：

| 字段 | 专用工具 |
|---|---|
| `/主角/金钱` | `earn_money` / `spend_money` / `manage_item(action="购买/卖出")` |
| `/主角/经验值`、`/主角/等级`、`/主角/所需经验值` | `try_level_up` / 奖励结算工具 |
| `/主角/属性/*`、`/主角/属性点` | `allocate_attribute_points` |
| `/主角/背包/-` | 禁止；对象背包必须用稳定 key + `manage_item` |
| `/主角/装备/*` | `manage_equipment` |
| `/主角/技能/*` | `commit_skill` |
| `/任务/*` | `manage_quest` |
| `/世界/地点`、`/世界/时间` | `change_scene` |

提示词提醒只能防君子；strict path 才能防模型手滑。

### 4. 派生值不写进 state

总攻击、防御、HP/MP/SP 上限、负重、价格折扣等派生值应运行时计算：

```txt
state 原始事实 → derived panel / get_status 返回
```

不要把派生值写回 state，否则装备/属性变化后很容易陈旧。

### 5. 状态排序只影响可读性

中文 key 多时建议写 `state-order.ts` 控制序列化顺序，方便人工 diff 和 playtest；但业务逻辑不能依赖对象顺序。

## 二、schema version

在 state 里保留元数据：

```json
{
  "元数据": {
    "schemaVersion": 3,
    "createdAt": "...",
    "updatedAt": "..."
  }
}
```

代码里维护：

```typescript
export const CURRENT_STATE_SCHEMA_VERSION = 3;
```

`getState()` 发现旧版本时不要自动“猜着读”，而是抛出明确错误：

```txt
StateMigrationRequiredError: 当前存档 schemaVersion=2，需要迁移到 3。请切换 debug toolset 后调用 migrate_state。
```

自动静默迁移看似方便，但会让回退/测试/玩家存档问题更难定位。推荐显式迁移。

## 三、migration 设计

### 迁移文件结构

```txt
engine/core/
├── initial-state.ts
├── state-schema.ts
├── state-version.ts
├── state-migrations.ts
└── legacy-migrations.ts   # 旧字段形状转换，仅 migration 调用
```

### 迁移函数模式

```typescript
export interface StateMigration {
  from: number;
  to: number;
  description: string;
  migrate(raw: unknown): Record<string, unknown>;
}

export const migrations: StateMigration[] = [
  {
    from: 1,
    to: 2,
    description: "旧同伴字段 → 核心系统；装备槽位标准化",
    migrate(raw) {
      const state = structuredClone(raw) as Record<string, unknown>;
      migrateLegacyFateCompanion(state);
      migrateLegacyEquipmentSlots(state);
      state.元数据 = { ...(state.元数据 as object), schemaVersion: 2 };
      return state;
    },
  },
];
```

迁移必须是：

- **确定性**：同一个旧存档多次迁移结果一致。
- **可测试**：fixture 输入 → 当前 schema 输出。
- **可审计**：每个版本写 description。
- **不调用 LLM**：迁移是代码，不是叙事推理。

### 迁移工具

把 `migrate_state` 放在 `debug` 或 `setup` toolset，不进 `always`：

```typescript
migrate_state({ dryRun?: boolean })
```

返回：

- 当前版本
- 目标版本
- 将执行的 migration 列表
- dryRun diff 摘要
- 成功后写入当前 state

同时提供只读工具：

```typescript
get_state_schema()
```

用于开发者/GM 查看当前 schema 和受保护路径，但同样不应常驻。

## 四、旧兼容只在 migration 中

错误做法：

```typescript
// ❌ runtime fallback 长期残留
export function getEquipmentSlot(item) {
  return state.装备?.武器 ?? state.装备?.武器槽 ?? state.装备?.主手;
}
```

正确做法：

```typescript
// ✅ migration 把旧槽位一次性改成当前槽位
migrateLegacyEquipmentSlots(raw);

// runtime 只读当前槽位
return state.主角.装备.武器1;
```

输入归一化可以保留，例如用户说“饰品”时工具自动选择 `饰品1/2/3`；但这不是旧 state 兼容，而是自然语言输入归一化。

## 五、测试建议

至少写：

```txt
scripts/test-state-core.js
scripts/fixtures/state-v1-legacy.json
scripts/fixtures/state-current.json
```

覆盖：

- `INITIAL_STATE` 符合 schema。
- 非法 root patch 被拒绝。
- 专用工具保护路径被拒绝。
- 旧 schemaVersion 会触发 `StateMigrationRequiredError`。
- `migrate_state` 能把 v1/v2 fixture 迁到当前 schema。
- 迁移后旧字段不存在，例如 `/旧同伴` 被删除。
- 派生值不落盘。

## 六、发布与玩家存档

发版包含 breaking state 变化时：

1. bump `CURRENT_STATE_SCHEMA_VERSION`。
2. 添加 migration。
3. 更新 `CHANGELOG.md`，写清玩家需要调用 `migrate_state` 或启动流程会提示。
4. 增加 fixture 回归测试。
5. release 前跑 `npm test`。

不要把“旧版本字段仍可读”当作长期兼容承诺。互动卡运行时由工具签名和当前 schema 引导，保持当前结构干净比无限兼容更重要。
