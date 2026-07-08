# 工程纪律

TS 默认不等于安全。迁移产物只要包含 TypeScript，就必须启用严格工程基线；不过检查不算完成。

## TypeScript 基线

必须开启：

- `strict`
- `noUncheckedIndexedAccess`
- `noUnusedLocals`
- `noUnusedParameters`
- `isolatedModules`
- `verbatimModuleSyntax`
- `noEmit`

建议开启：

- `strictNullChecks`
- `noImplicitAny`
- `noFallthroughCasesInSwitch`
- `forceConsistentCasingInFileNames`

## 工具链

项目应提供等价脚本：

```txt
typecheck
lint
format:check
deadcode
```

工具可替换；以等价检查能力为准，不以某个具体工具名为准。deadcode 用 knip 或等价工具扫未引用导出和死文件；重构后跑一次，扫出来直接删。

完工前 typecheck/lint/format 必须全过。lint 至少应覆盖 correctness/suspicious，并启用类型感知规则；必须拦截 unsafe assertion。

## 类型纪律

- 业务代码零 `any`；外部 `any/unknown` 在边界立即窄化。
- `as` 只能贴近验证点使用，或带安全理由。
- 边界窄化用共享 schema 模块（如 TypeBox tagged union + 统一 parse 入口），不为每个工具克隆手写 assert。手写 assert 会繁殖：实战项目迁移到 schema 校验时一次删掉 70 多个。
- state/领域类型从 schema 派生（TypeBox `Static<typeof SCHEMA>`），schema 是类型唯一事实源。不维护手写平行类型 + parity 测试对齐双轨——双轨必漂移，parity check 是在给本不该存在的重复买保险，逐域迁移到派生类型后就该整个删掉。手写类型只留给没有 schema 的纯内部结构。
- 禁止 unsafe type assertion；能用 type guard / assert function 窄化就不用 `as`。
- 禁止 `as unknown as T`。
- 导出函数标注返回类型。
- 状态多形态用 discriminated union，不用 optional 字段猜。
- 索引访问必须处理 `undefined`。

## 结构纪律

- `extension.ts` 只注册。每个工具一个文件，契约（name/description/parameters）与实现同文件；`tools/registry.ts` 只是注册清单，不长逻辑。
- 不堆 god module：类型词汇表、store 生命周期、session 持久化、边界归一化、ID 分配各归各文件。某文件既导出类型又导出 store 又导出胶水时就该拆了。
- engine 纯函数优先；领域事件收 `(draft, event)`，不读写 store；确定性逻辑可单测。
- 长跑项目维护 `CONTEXT.md` 领域词汇（每个术语带「不要叫成什么」）和 `docs/adr/`；命名和拆分跟着词汇走。
- 目录名拒绝歧义泛名。长跑项目长大后集中返工过的命名：`data/`→`world-data/`（与运行时 state 混）、`state/`→`runtime/`（它装的是 debug 导出不是 canonical state）、`agents/`→`prompts/`（装的是 prompt 素材，与 `.pi/agents/` 的真 subagent 定义撞名）、`engine/direction/`→`engine/render/`、`tools/state/`→`tools/settlement/`。新项目直接用无歧义名；engine 变大后按领域拆子目录（actor/scene/turn/memory/secrets/economy/backstage），prompt 素材按 pass 分目录、文件名对齐 preset 模块 id。
- 长跑项目的成熟形态（以旗舰实战仓为准，供长大时对照，不是起步模板）：

  ```txt
  engine/core/<domain>/      # actor/scene/turn/memory/secrets/economy/backstage…
  engine/prompt-assembly/    # 注入栈组装
  engine/render/             # 两段式渲染侧
  engine/audit/  engine/debug/
  tools/settlement/  tools/lookup/  tools/debug/  tools/runtime/
  prompts/<pass>/            # 素材按 pass 分目录；preset-<pass>.json 对齐模块 id
  world-data/                # 静态世界数据与索引（含 card-ir/runtime-plan）
  runtime/                   # debug 导出快照，gitignored，非 canonical state
  extensions/<capability>/   # compaction-policy/player-panel/subagents/two-pass-render…
  skills/<protocol>/SKILL.md # start-game 之外可拆输入协议/时间感等玩法协议
  tests/  docs/adr/  CONTEXT.md  CHANGELOG.md
  ```

- 不写「以后可能用」的抽象。
- 死代码、注释掉的代码、未注册工具直接删。
- 注释解释为什么，不复述代码。

## Prompt / 工具体量纪律

非 GPT 模型在重结算回合普遍跑得慢、思维链异常冗长，根因常是 prompt 栈过重 + 工具 description 堆「【必须调用的场景】/【严禁的行为】」式长清单。

- **checklist 体例是 reasoning-bait**。这种清单会诱导模型动手前先把整套规约逐条复述一遍。工具 description 收成「一行用途 + 使用边界 bullet + 严禁 bullet」的紧凑格式；prompt 模块只把规则讲清一次，不靠反复堆清单「加固」。
- **纯静态瘦身，不引入动态前缀**。体量超重就禁掉无关模块、压缩文字（实测：结算主干 42558→16768 字符 -60%，工具 description -33%，行为/schema 零改动）。绝不按当轮输入改 prompt 前缀：有项目试过 meta-turn 动态裁剪随后整体回退——任何按输入变前缀的逻辑都击穿 prefix cache，每回合重新计费整段系统提示。
- **注入栈用测试钉死**。固定模块数（如 `injected.length === 11`）+ slot 顺序，让「删文字」类改动一旦越界立即被 gate 拦下。瘦身的安全边界靠 packet 契约、工具 schema 宽松性、注入栈结构这些机器可校验项兑现。
- 这条与「Prompt 不是防线」一脉相承：真纪律落在 engine ledger（见 `evented-runtime.md`），prompt 只负责把规则说清楚一次。

削减推理耗时有两个独立杠杆，可叠加：

- **输入侧：瘦身 prompt / 避免 checklist reasoning-bait**（本节）——减少模型动手前要复述/消化的材料量。
- **输出侧：卡掉原生思维链**（见 `two-pass-rendering.md` 「压制渲染侧原生思维链」）——在不需推理的环节（如 Pass B 纯 prose 渲染）用 prefill 闭合标签让模型跳过 CoT 直接出文。区分哪些环节该保留推理（结算/裁决）、哪些该关推理（渲染）。

## State 纪律

- 当前 schema 是唯一运行时结构。
- 旧字段只在 migration 中读取。
- protected paths 不能裸 patch。
- 派生值不落盘。
- migration 是确定性代码，不交给 LLM 猜。

## 绕过规则

`@ts-ignore`、lint disable、format ignore 只允许短期局部使用，并且必须写原因。无原因视为不合格。

## 完工门槛

- typecheck 零错误。
- lint 零错误。
- format check 零差异。
- 确定性逻辑有测试或可复现校验。
