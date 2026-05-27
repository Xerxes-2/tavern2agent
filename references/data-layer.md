# 数据层

目标：结构化保存设定，用工具查，用 `content` 返回给模型。不要让 GM 运行时靠 `bash/read` 翻文件，也不要把大 JSON 塞进 prompt。

## 原则

1. `data/*.json` 是世界观、NPC、地点、物价、规则的权威源。
2. GM 只通过 `lookup`/领域工具读取预设事实。
3. 大数据集用索引查，再按需返回正文。
4. 结果放 `content`；`details` 只给 TUI/日志。
5. 工具 description 写清必须调用场景和禁编规则。

## 目录

```txt
data/
├── locations.json
├── characters.json
├── factions.json
├── monsters.json
├── items.json
├── game_rules.json
└── index.json              # 名称/别名/关键词 → 文件 + key + 摘要
```

大卡可拆：`location_index.json`、`npc_index.json`、`dlc_index.json`。索引用脚本生成，不手写。

索引条目：

```json
{
  "name": "瓦伦蒂亚",
  "aliases": ["炼金术师之城"],
  "type": "location",
  "path": "locations.json#/瓦伦蒂亚",
  "summary": "以炼金术师公会闻名的城市……"
}
```

## 工具

中小型卡优先一个统一工具：

```ts
lookup({ query: string, type?: "location" | "npc" | "faction" | "monster" | "rule" | "dlc" })
```

大型卡才拆领域工具：

| 工具 | 查 |
|---|---|
| `lookup_location` | 地点/建筑/路线 |
| `lookup_npc` | NPC/组织成员 |
| `lookup_rule` | 术语/货币/战斗规则 |
| `get_dlc_info` | DLC/启用模块 |
| `lookup_item` | 装备/材料/技能模板 |

拆分前提：每个工具有清晰触发场景。否则统一 `lookup`。

## 返回格式

```ts
return {
  content: [{
    type: "text",
    text: JSON.stringify({ found: true, entries, guidance }, null, 2),
  }],
  details: { entries },
};
```

不要只把事实放 `details`。模型主要看 `content`。

## 校验

- 每个 index path 能 resolve。

- 常见别名能命中。
- DLC 关闭时专属条目不可见。
- 无结果时给候选，而不是空字符串。

## Prompt 只放纪律

```md
- 提及预设地点/NPC/规则时先 lookup。
- 未经 lookup 的预设事实不存在。
- 可以即兴路人细节；不能改写预设事实。
```

正文放 data，动态事实放 state，表达交给 GM。
