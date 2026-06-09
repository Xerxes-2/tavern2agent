# 数据层

目标：给 GM 一个权威事实读取层，用工具查，用 `content` 返回给模型。不要让 GM 运行时靠 `bash/read` 翻文件，也不要把大 JSON 塞进 prompt。

数据层不一定全是本地 JSON。v2 可以把“知识库”拆成两类事实源：

```txt
curated local data   卡片作者给定的世界事实、规则、NPC、地点、秘密
external research    现实题材、开放网络资料、GitHub/论文/新闻等可查事实
```

本地 data 管 canonical game facts；网络搜索工具管外部现实事实。不要把两者混成一坨 prompt 知识库。

## 原则

1. `data/*.json` 是卡片内世界观、NPC、地点、物价、规则的权威源。
2. GM 只通过 `lookup`/领域工具读取预设事实。
3. 现实世界 / 开源项目 / 活资料优先走 web/search/fetch/code-search 工具，不手工复制成静态知识库。
4. 大数据集用索引查，再按需返回正文。
5. 结果放 `content`；`details` 只给 TUI/日志。
6. 工具 description 写清必须调用场景和禁编规则。

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

## 本地 lookup 工具

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

## 外部 research 工具

当卡片题材依赖现实世界、近期资料或开源项目时，不要把外部知识复制成 `data/world.json`。给 GM 一个只读 research seam：

| 工具 | 用途 |
|---|---|
| `web_search` | 现实题材、新闻、地理、历史、行业背景，返回带来源摘要 |
| `fetch_content` | 指定 URL / 文档 / PDF / YouTube 内容抽取 |
| `code_search` | 开源库 API、实现细节、GitHub/StackOverflow 示例 |
| `lookup` | 卡片作者给定的 canonical game facts |

使用规则：

- 现实题材：允许 research；查到的事实要标来源，不能自动写入 canonical state。
- 虚构原作 / 卡片自设：默认禁止 web，避免污染作者设定；只查本地 data。
- 混合题材：外部资料只补现实背景，不覆盖卡片 canonical facts。
- 任何 research 结果都是只读证据；若要进入世界状态，必须由 GM 通过领域事件记录为 rumor、memory、clue 或 setting update。

不要把 web search 当作“更大的世界书”。它是按需取证工具，不是每轮注入的知识库。

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
- 现实题材需要外部事实时先 research，并在叙事中只使用已确认事实。
- 虚构世界默认不用 web；卡片 data 的 canonical fact 优先于外部资料。
- 可以即兴路人细节；不能改写预设事实。
```

正文放 data，动态事实放 state，外部资料按需 research，表达交给 GM。
