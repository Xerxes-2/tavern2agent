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
- 边界窄化用共享 schema 模块（如 TypeBox tagged union + 统一 parse 入口），不为每个工具克隆手写 assert。手写 assert 会繁殖：fsn 迁移到 schema 校验时删掉 70 多个。
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
- 不写「以后可能用」的抽象。
- 死代码、注释掉的代码、未注册工具直接删。
- 注释解释为什么，不复述代码。

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
