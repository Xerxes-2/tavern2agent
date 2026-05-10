# MVU 条目 → Engine 模块映射详解

MVU 条目（`[mvu_update]` 和 `[mvu_plot]`）是卡片作者写给 LLM 的「系统设计文档」。
**不要当垃圾丢掉——它是你的设计文档。** 逐条用 `scripts/get_entry.py` 读取后自行判断。

## 三大去向

| 内容性质 | 去向 | 示例 |
|---------|------|------|
| **可计算的** | engine 模块 | 骰子公式、伤害计算、属性修正、经验值曲线 |
| **叙事指引** | prompt（GM 或 narrator） | 剧情推进规则、文风设定、并行事件 |
| **酒馆补丁** | 丢弃 | 强化思考链、JSON Patch 格式、UpdateVariable 标签、EJS 模板 |

## 常见内容 → engine 模块映射

这是**参考**，不是模板。你对每条条目做判断。

### 骰子系统
**识别**：`{{roll:2d6}}`、掷骰规则、属性检定、DC 分级
**→ engine/dice.ts**
```
- check(attrValue, targetDC, bonus?) → { success, level, roll, total }
- rollDice(count, sides) → number[]
- attrMod(value) → number（(value - 10) / 2 向下取整）
```

### 战斗系统
**识别**：伤害公式、HP 管理、护甲减伤、暴击规则
**→ engine/combat.ts**
```
- calcDamage(attackerStr, weaponAtk, defenderArmor, defenderEndurance) → { damage, absorbed, net }
- applyDamage(target, damage) → state delta
- checkKO(target) → boolean
```

### 好感度系统
**识别**：好感度范围（如 -100~100）、增减规则（如每次 ±5）、态度阈值
**→ engine/affection.ts**
```
- adjustAffection(characterId, delta) → newValue
- getAffectionLevel(characterId) → "敌对" | "中立" | "友好" | ...
```

### 经济/声望/经验值
**识别**：收入公式、声望计算、等级经验曲线
**→ engine/economy.ts**（或拆为多个文件）

### 死亡回溯
**识别**：死亡条件、回溯规则、存档点机制
**→ engine/death.ts**
```
- checkDeath(state) → boolean
- triggerRewind(state) → newState（截断事件流到存档点 + 注入死亡事件）
```

### 任务系统
**识别**：任务生成规则、完成条件、章节推进
**→ engine/quest.ts**

## 轻量方案：MVU → INITIAL_STATE（不写 engine 模块）

如果 MVU 条目只描述**键值状态**（好感度、计数器、任务标记、地点/时间），**没有**骰子/伤害/经济公式：

1. `get_entry.py` 读所有 `[mvu_update]` 条目的 `content`
2. 找到变量定义块（JSON / YAML / `name: 默认值` 列表均可）
3. 直接拷成 SKILL.md「轻量方案」中 `INITIAL_STATE` 的字面量。**不要**生成 dice.ts/combat.ts/economy.ts——那些条目本身就不该存在
4. 对 MVU 里描述「何时变化」的自然语言（如「每次帮助 +5」），**不要**翻译成代码——写成 GM prompt 里的一行规则，让 agent 自己判断后调 `update_status`

判断边界：条目里出现 `{{roll:...}}`、伤害公式、阈值分级（DC/暴击/经验曲线）→ 升级到完整 engine 方案；只有「±N」「设为 X」→ 留在轻量方案。

## 变量定义 → engine/state.ts（完整 engine 方案）

MVU 条目中的 JSON Schema 或变量列表是**初始状态的蓝图**。

### 提取方法
1. 用 `get_entry.py` 读 MVU 条目
2. 找到变量定义块（通常是 JSON 或 YAML 结构）
3. 转化为 `initialState()` 函数返回的对象

### 常见模式

**简单键值对**：
```
好感度: 0
时间: "上午 10:00"
地点: "学院正门"
```
→ 直接转为对象。

**嵌套结构**（Re:0 风格）：
```json
{
  "主角": {
    "姓名": "{{user}}",
    "生命值": { "当前值": 10, "最大值": 10 },
    "属性列表": { "力量": 10, "敏捷": 10 }
  },
  "关系列表": {},
  "时间": { "年月日": "", "时间": "" }
}
```
→ `initialState()` 返回完整嵌套对象。

**变更约束**：
```
单回合变化限制: "所有数值型变量单回合变化绝对值不得超过 15 点"
```
→ 写成 `dispatch()` 的校验逻辑。

## 必须丢弃的内容

### 强化思考链 (COT)
```
<强化思考要求>
step1: 我是否已经知道了当前变量内容。
step2: 我是否已经进行认知隔离。
...
```
→ agent 自己会推理。丢弃。

### JSON Patch / UpdateVariable 输出格式
```
<变量修改格式>
rule: you must output the update analysis and the actual update commands at once
the update commands works like the JSON Patch (RFC 6902) standard
```
→ agent 调工具 dispatch 事件。丢弃。

### EJS 条件模板
```
<%_ if (getvar('月宫绾音.拥有联系方式') == true) { _%>
线上聊天气泡: ...
<%_ } _%>
```
→ 这是酒馆的条件注入逻辑。提取条件描述（如「当用户拥有联系方式时显示聊天气泡」），**丢弃模板代码**。

### 角色强制输出格式
```
<角色登场>
请必须在下一次剧情开始之前输出下一次剧情要出现的主要角色。
<出场角色> 爱蜜莉雅,帕克 </出场角色>
```
→ agent 自己判断何时引入角色。丢弃。

### `__结束__` 标记
→ 酒馆用来分隔剧情和变量更新的标记。丢弃。
