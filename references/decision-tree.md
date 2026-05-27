# 方案判定

主表见 `SKILL.md`。这里处理临界场景。

## 信号

- 有 `[mvu_update]` / `[mvu_plot]` / Zod schema：至少 light。
- 有骰子、战斗、伤害公式、经济流通、多字段联动：standard。
- 状态键 ≤10 且只有简单加减：light。
- 只有 1-2 个偶发 roll：light 或 prompt，别过度工程。
- 卡反复强调“严格公式/禁止自由发挥”：偏 standard。
- 死亡回溯/读档/撤销：不升档；用 session tree/fork。
- 周目继承记忆：加 `meta/persistent.json` 或 permanent custom entry。
- 非 MVU 自定义变量：按语义映射，不单开方案。

## 样例

| 特征 | 档位 |
|---|---|
| 纯地理/势力/NPC，无变量 | prompt |
| 只有开局选阵营/难度 | prompt + start skill |
| 30+ 键值状态，简单 ± | light |
| 偶发 `{{roll:1d6}}` 占卜 | light |
| 伤害公式 + 装备护甲 + 命中 | standard |
| 死亡循环只是叙事 | 按计算复杂度判 |
| 真回档到存档点 | 按计算复杂度判 + session-backed state |
| 周目保留记忆字段 | 上者 + persistent meta |
| 多结局章节读档 | session-backed state |
