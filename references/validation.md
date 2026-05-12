# 产出校验

## 残留检测

```bash
# 一行 grep 扫残留
grep -rnE "UpdateVariable|JSON Patch|<%_|\{\{getvar:|\{\{setvar:|__结束__|强化思考要求|认知隔离" \
  agents/ engine/ data/ 2>/dev/null && echo "↑ 有残留，逐条核对" || echo "✓ 无残留"
```

> 以下字段出现在 `engine/state.ts` / `engine/types.ts` 中且**用于本卡游戏逻辑**（非照抄 Re:0 示例），属于合理命中：`魔女残香`、`死亡回溯计数`、`is_changed_chapter`、`好感度`、`生命值`、`魔法值` 等。仅当出现在**非 Re:0 的卡**中时才需核查。

```bash
# Re:0 特有字段核查
grep -rnE "魔女残香|死亡回溯计数|is_changed_chapter" agents/ engine/ data/ 2>/dev/null
```

逐条核对：是本卡 schema 定义的字段 → 保留；是 ts-engine.md 的 Re:0 例子照搬 → 重写。

## 人工检查清单

- [ ] `agents/gm.md` 核心规则 ≤5 条
- [ ] 如有游戏系统则 `agents/narrator.md` 存在且 `tools: []`
- [ ] engine 模块覆盖 MVU 计算规则
- [ ] state schema 与 MVU 变量定义一致
- [ ] 角色数据按需拆分到 `data/characters.json`（≥5 个角色时）
- [ ] `first_mes` 的 HTML/状态面板已剥离，纯叙事（或合成叙事）写入 `narrator.log`
- [ ] `skills/开局.md` 已生成，且正确反映 user 卡/设置需求
- [ ] 需要 user 卡时 `data/user.json` 已生成（含已知字段，缺失字段标注 `"TODO"`）
- [ ] `[initvar]` 已被读取并转化为 `INITIAL_STATE`（如有）
- [ ] `tavern_helper.scripts` 中 Zod 脚本已被提取（如有）
- [ ] `tavern_helper.scripts` 中游戏系统脚本已被处理（如有）
- [ ] `regex_scripts` 中的游戏数据已被提取（如有）
- [ ] 章节剧情模板未全量注入 prompt（如有）
