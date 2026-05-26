# CodeAct 范式：标准方案的沙箱形态

标准方案不再用「N 个 engine 工具 + 按场景切 toolset」的形态。改用**单个 `code_act` 工具 + node:vm 沙箱**——GM 每轮写一段 JS，在沙箱里组合任意操作。

实际经验：从 tool-calling 形态转 CodeAct 之后，prompt 和 engine 代码**双瘦身**。所以标准方案默认就上 CodeAct，不再保留多工具形态。

> **何时不用 CodeAct**：见 SKILL.md §三决策表。纯 prompt / 轻量档不要套沙箱——单轮就一次 ±1 的卡，建沙箱是负收益。

---

## 一、三层 API（核心架构）

```
Layer 3：场景层 scene(type, params)
  ↑ 输入：高层意图（"今晚去涩谷开 LIVE，观众 120 人"）
    输出：结算 + 事件骰子 + 叙事钩子

Layer 2：组合层 post(...)  advance(...)  grow_fans(...)  set_condition(...)
  ↑ 输入：语义参数
    输出：多字段联动写入 + 自动计算

Layer 1：原语层 adjust_money(delta)  adjust_*(delta)  patch(ops)
                status()  lookup(type, query)  log(...)
  ↑ 输入：精确数值 / 单字段路径
    输出：原子读写
```

**设计原则**：

1. **三层都暴露**——只给场景层是把灵活性卖了换便利，只给原语层是把组合性的代码工作扣在 LLM 头上。
2. **场景层覆盖 80% 日常**——LLM 优先调用。
3. **原语层兜底**——场景表覆盖不到的奇怪操作，LLM 用原语原子组合。
4. **组合层是「常用的非平凡组合」**——比如 `post()` 内含发帖+互动数据生成+涨粉判定，单独让 LLM 拼这个组合既重复又易错。

**硬底线**（SKILL.md Q4 已决议）：

- **组合层 + 原语层必须**——没它们沙箱等于把 patch 搬进 JS。
- **场景层视题材**——题材里能否归纳出「持续若干分钟、有结算 + 可能触发事件」的活动单元？有就上 scene（idol 卡的公演/活动/日常，战斗 RPG 的战斗/探索/休息）；没有就略，组合层承担"常用多步操作"的角色。

---

## 二、CodeAct 的八种独特能力

这些是 tool-calling 范式**根本做不到**或**做起来巨痛**的能力。沙箱 API 的设计要围绕它们组织。

### A. 对状态做计算

LLM 心算数学不可靠——`1280 + 9500` 时不时给出 `10880`。沙箱里这是确定的。

```js
const s = status();
const daysLeft = 30 - s.世界状态._date.day;
const projectedExpense = daysLeft * 3000;
if (s.个人信息.财务状况 < projectedExpense) {
  log(`⚠️ ${daysLeft} 天后赤字 ¥${projectedExpense - s.个人信息.财务状况}`);
}
```

→ 沙箱必须暴露 `status()` 返回**完整 state clone**。

### B. 真随机 on-demand

LLM 「我掷一个 d20」出名不随机，偏好叙事方便的数字。`Math.random()` 是真随机。

```js
const dice = Math.random();
if (dice < 0.05) earnMoney(50000, '路上捡到钱包获谢礼');
else if (dice < 0.2) spendMoney(3000, '丢钱包');
```

→ node:vm context 默认就有 `Math.random()`，无需特别暴露。

### C. 反应性级联（事件触发事件）

scene 返回的事件，GM 可以**在同一回合内**根据具体结果做后续动作。tool-call 范式做不到——每轮一个动作，下一轮才能回应。

```js
const live = scene('live_show', { venue: '涩谷', audience: 120 });

if (live.events.some(e => e.id === 'scout_encounter')) {
  set_relation('add', '星探·???', '潜在机会', '在 LIVE 后递了名片');
  patch([{ op: 'add', path: '/职业发展/当前风险状态', value: '面临选择：跳槽？' }]);
}
if (live.settlement.fanGrowth > 100) {
  post('今天的演出，能站在那个舞台上真的太开心了～');
}
```

→ **所有写函数必须返回结构化结果**（`{ before, after }` / `{ settlement, events, hooks }`），供后续判断使用。这是 §四「沙箱实现要点」之首。

### D. 上下文节流

`get_status` tool 会把整棵 state（往往 2-3KB）灌进 LLM context。CodeAct 只摘需要的字段 log。

```js
const s = status();
log(`¥${s.个人信息.财务状况} | 粉丝${s.社交媒体.总粉丝数} | ${s.世界状态.日期}`);
```

长会话场景下每轮节省 90% state 字节 = 延长有效上下文寿命。

→ 不要提供 `get_status_field(path)` 这类"按字段查"工具——LLM 在沙箱里 `status()` 后自己摘。

### E. 幂等检查 + 状态卫生

tool-call 模式做「读 → 判断 → 也许写」要两轮，沙箱一段代码原子完成。

```js
const s = status();
if (s.隐私记录.初次记录['kiss'] === '无') {
  patch([{ op: 'replace', path: '/隐私记录/初次记录/kiss', value: '雨夜的涩谷站' }]);
}
```

→ 沙箱必须暴露 `patch(ops)` 作为兜底——JSON Patch RFC 6902 的灵活性 + 沙箱里的条件控制流，是状态卫生的关键组合。

### F. 错误优雅降级

tool-call 失败 = LLM 下一轮看到错误信息重试。CodeAct 里 try-catch 当场降级。

```js
try {
  const t = lookup('term', '炎上');
  log(t[0].definition);
} catch {
  log('查无此词，凭叙事直觉处理');
}
```

→ **lookup 等查询失败必须 throw**——不要返回 `null` 让 LLM 检查。这样 try-catch 才是有意义的控制结构。

### G. 时间压缩（蒙太奇叙事）

「一周后」式时间跳跃，tool-call 要 5 轮，沙箱一段代码：

```js
scene('daily_activity', { minutes: 1440 });
scene('live_show', { venue: 'small_venue', audience: 30 });
scene('daily_activity', { minutes: 1440 * 3 });
scene('fan_event', { audience: 25 });
scene('daily_activity', { minutes: 1440 });
```

每个 scene 独立结算+掷骰，七天后 GM 拿到 5 份「场景结算 + 钩子」，写一段浓缩叙事。

→ Prompt 必须教会 GM：想做时间跳跃 = 写一段 scene 序列，不要拆成多轮工具调用。

### H. 自动生成叙事张力提示

让 GM 给自己写"下一段叙事 brief"——把状态扫描结果当作叙事焦点提示。

```js
const s = status();
const tensions = [];
if (s.个人信息.财务状况 < 30000) tensions.push('财务压力');
if (s.社交媒体.近期增长趋势 === '停滞') tensions.push('粉丝瓶颈');
if (Object.keys(s.隐私记录.敏感风险标签).length >= 2) tensions.push('风险累积');
if (tensions.length) log(`📍 本轮张力点: ${tensions.join(' / ')}`);
```

→ **CodeAct 范式下不再单独写 `engine/attention.ts`**——本能力吸收了原 attention.ts 的"每轮扫描 + 注入提醒"职责。完整迁移说明见 `ts-engine.md` §「注意力调度（轻量方案可选）」。

---

## 三、沙箱实现要点（五条硬底线，少一条沙箱就坏）

### 1. 写函数必须返回结构化结果

```js
// ❌ 错
adjust_money: (delta) => { state.财务 += delta; }
// 返回 undefined，LLM 没法做条件判断（§二·C 反应性级联失效）

// ✅ 对
adjust_money: (delta) => {
  const { before, after } = applyMoneyDelta(delta);
  output.push(`💴 ¥${before} → ¥${after}`);
  return { before, after };
}
```

### 2. 错误必须 throw，不要返回 null

```js
// ❌ 错：返回 null 让 LLM 检查
// ✅ 对：throw 让 try-catch 有意义
lookup: (type, q) => {
  const result = ...;
  if (!result) throw new Error(`未找到 "${q}"`);
  return result;
}
```

### 3. 写函数自动 log

每个写函数内部 `output.push(...)` 一条人类可读日志。**不要让 LLM `log(adjust_money(...))` 包一层**——会出 `[object Object]`。这条 prompt 严禁清单里要点名。

### 4. `status()` 返回完整 clone

不要返回引用——LLM 可能误改 state object。每次 `status()` 返回 `structuredClone(state)`。

### 5. 沙箱超时 15 秒

LLM 写的代码偶尔无限循环或忘 break。

```js
script.runInContext(context, { timeout: 15000 });
```

### 6. 三层 API 的签名约定用 `.d.ts` 表达，不用自然语言列函数

沙箱里暴露的函数有什么、参数/返回值是什么形状 — **单一权威源是一份 `.d.ts` 类型声明**（实战经验）。该 `.d.ts` 同时是：

- 沙箱 API 文档
- `code_act` 工具 `description` 的主体（直接嵌入，让 LLM 每轮看到带类型的签名）
- TS 沙箱实现的外部接口声明（可被 tsc 类型检查保障一致性）

```ts
// engine/codeact-sandbox.d.ts 示例

// ─── 原语层 ───
declare function status(): Readonly<WorldState>;
declare function log(message: string): void;
/** 受 protected paths 保护：击中受保护路径会 throw */
declare function patch(ops: PatchOp[]): void;
/** 未命中则 throw，用 try-catch 优雅降级 */
declare function lookup(type: 'term' | 'npc' | 'location', query: string): LookupEntry[];
declare function adjust_money(delta: number, reason?: string): { before: number; after: number };

// ─── 组合层 ───
declare function post(summary: string, controversial?: boolean): { fanGrowth: number; engagement: number };
declare function advance(minutes: number, reason?: string): { newTime: string; tensionsLogged: string[] };
declare function grow_fans(level: 'small' | 'medium' | 'big'): { before: number; after: number };

// ─── 场景层（用「映射 + 泛型」表达不同 scene 返回不同结算）───
interface SceneResults {
  live_show: { settlement: { fanGrowth: number; income: number }; events: SceneEvent[]; hooks: string[] };
  fan_event: { settlement: { fanGrowth: number; income: number }; events: SceneEvent[]; hooks: string[] };
  daily_activity: { settlement: { tensionsLogged: string[] }; events: SceneEvent[]; hooks: string[] };
}
interface SceneParams {
  live_show: { venue: string; audience: number };
  fan_event: { audience: number };
  daily_activity: { minutes: number };
}
declare function scene<K extends keyof SceneResults>(type: K, params: SceneParams[K]): SceneResults[K];
```

**为什么这个比自然语言函数列表好：**

- LLM 看到 `scene()` 返回类型有 `events: SceneEvent[]`，**自然推导**下一步可以 `result.events.some(e => e.id === 'xxx')`——反应性级联（§二·C）的前提在签名里就明示了。
- `adjust_money` 返回 `{ before, after }` 在类型里，不需要在 description 里写「该函数返回一个对象，包含 before 和 after」，减少自然语言歧义。
- `lookup()` 未命中则 throw——这个契约可以在类型上方加一行 JSDoc，LLM 读到后在脚本里自然包 try-catch（§二·F）。
- 场景层多 scene 类型用「`SceneResults` 映射 + 泛型」，能表达「不同 scene 返回结构不同」——这是自然语言表达不了的。
- TS 沙箱实现的函数签名跟 `.d.ts` 一致可以用 tsc 类型检查保证，prompt 与实现不脱节。

**落地方式**：`code_act` 工具的 `description` 字符串里直接嵌入这份 `.d.ts` 文本（`readFileSync` 读入或拼进去），上面加三段式 description（必须调用 / 严禁行为 / 三层优先级，见§五）。LLM 每轮看到的就是「约束原则 + 完整类型化签名」。

---

## 四、与轻量方案/底层基建的契约

CodeAct 不重写底层，只**重组对外形态**。沙箱里的写函数最终走的还是 `ts-engine.md` 那套基建：

1. **In-memory state + globalThis store** 不变——沙箱里的 `adjust_money`/`patch` 最终调用的是 `patchState()`，跟轻量方案完全一样。
2. **`code_act` 工具的 execute** 在脚本跑完后，把 dirty state dump 到 `toolResult.details["<card-slug>-state"]`——跟轻量方案的 `attachStateSnapshot` 包装器机制一致。
3. **session-backed 持久化协议不变**——hook 兜底（turn_start / agent_end / session_compact）原样照用。
4. **subagent 不持有 `code_act` 工具**（SKILL.md Q5 已决议）——状态写入仍由 GM 在主沙箱完成；subagent 需要状态变化时返回结构化建议给 GM。

→ 把底层基建当成"沙箱以外的世界"。沙箱只是 GM 那一轮与状态交互的新形态。

---

## 五、Prompt 工程要点

### 三层优先级（写进 `agents/gm-context.md`）

```
优先级 1: scene(type, params)   ← 80% 日常活动走这个
优先级 2: post() / advance() / grow_fans() 等组合层
优先级 3: adjust_* / patch() 原语层  ← 兜底
```

作为 GM 每轮"叙事轮第一选择"。

### 时间压缩模式

```
想做「一周后」「下个月」式跳跃 → 写一段 scene() 序列，不要拆成多轮工具调用。
每个 scene 独立结算+掷骰，最后写一段浓缩叙事。
```

### 反应性级联 few-shot（写进 `agents/gm-rules.md`）

```js
const result = scene('xxx', { ... });
if (result.events.some(e => e.id === 'xxx')) {
  // 触发后续连锁
}
if (result.settlement.xxx > threshold) {
  // 数值超过门槛的后续
}
```

### 严禁清单（`agents/gm-rules.md` 末尾）

- ❌ 用 `log(scene(...))` 包裹场景调用 —— 会变成 `[object Object]`
- ❌ 单次脚本 > 15 秒（沙箱超时）
- ❌ `require` / `import` / `process` / `fs` 访问 host 文件系统
- ❌ 在 CodeAct 里写完整叙事决策 —— 叙事仍由 LLM 在沙箱外面的回复中完成；沙箱只产生「数值结果 + 钩子」供叙事引用

### `code_act` 工具的 description 工程

按 `pi-integration.md` §「工具 description 工程」四段式写（**最后一段 `.d.ts` 是本范式独有的 — 见 §三·6**）：

- **【必须调用的场景】**：状态发生任何变化时、需要掷骰时、需要时间推进时、需要时间压缩蒙太奇时
- **【严禁的行为】**：不要在叙事里给出"裸数值"（"+200 粉丝"）；不要不调用 `code_act` 就声称状态已改变；不要在脚本里写完整叙事
- **【三层优先级】**：scene > 组合 > 原语，按本表顺序选最高层
- **【沙箱 API 签名（权威）】**：直接嵌入 `engine/codeact-sandbox.d.ts`。三层函数的参数、返回值、可能报错，以类型声明为准，不重复写自然语言描述。

---

## 六、State 字段保护机制（protected paths）

CodeAct 暴露的 `patch()` 原语 = 全权 JSON Patch，绕过组合层 / 场景层的计算逻辑很容易。同一类「状态变化有规则」的场景（金钱、粉丝、装备、技能、任务、场景切换），必须把对应路径写进**保护清单**，由沙箱在执行 `patch(ops)` 前校验：

```js
const PROTECTED_PATHS = [
  '/经济/财务',         // 必须走 adjust_money
  '/社交媒体/总粉丝数',   // 必须走 grow_fans
  '/装备',              // 必须走专用组合函数
  // ...
];

// patch 实现里：
ops.forEach(op => {
  if (PROTECTED_PATHS.some(p => op.path.startsWith(p))) {
    throw new Error(`受保护路径 ${op.path}：请使用对应组合函数（adjust_money / grow_fans / ...）`);
  }
});
```

→ 跟 `state-schema-migrations.md` §「strict path 保护」是同一论点的 CodeAct 化身。专用工具变成沙箱里的专用函数，"绕过"行为同样要拒绝。

---

## 七、移植 checklist

迁移完成、对外说"标准方案落地了"之前**逐项核对**。本表已跟 SKILL.md §五完工自检对齐——SKILL.md 那边会再点一遍这些项，本表保留作为"沙箱设计者视角"的快速自查。

- [ ] **原语层 + 组合层齐全**（硬底线）；如题材有 scene 单元，**场景层也齐全**
- [ ] **场景层有事件表**：事件带 condition 过滤 + weight 加权 + 冷却机制
- [ ] **所有写函数返回结构化结果**：`{ before, after }` 或更具体
- [ ] **lookup 失败时 throw**，让 try-catch 有意义
- [ ] **`status()` 返回 clone**，避免 LLM 改坏
- [ ] **沙箱超时 15 秒**，防止死循环
- [ ] **沙箱无 fs / process / require / import 出口**
- [ ] **写函数自动 log**，禁止 `log(scene(...))` 包裹（prompt 严禁清单已写）
- [ ] **`gm-context.md` 教会三层优先级**
- [ ] **`gm-rules.md` 给反应性级联 few-shot + 时间压缩 few-shot**
- [ ] **`gm-rules.md` 严禁清单写明** `log(scene(...))` / fs 访问 / 沙箱里写叙事
- [ ] **protected paths 设计完整**：经济/粉丝/装备/技能/任务等关键字段拒绝裸 `patch`，必须走对应组合函数
- [ ] **`code_act` 工具的 description 写了「必须调用 / 严禁行为 / 三层优先级」三段**，**后面拼了 `engine/codeact-sandbox.d.ts` 作为三层 API 的单一权威签名源**（§三·6）
- [ ] **沙箱写函数最终走 `patchState()` → in-memory store → session entry 持久化**，跟轻量方案共用同一链路（§四契约）
- [ ] **subagent 不持有 `code_act`**（如有 subagent），子代理只返回结构化建议

任何一项打不上 ✓，**继续做完再报告**。
