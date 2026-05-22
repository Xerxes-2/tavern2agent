# 数据层设计：让 LLM 查得到，数据才算存在

SillyTavern 世界书依赖关键词触发；agent 项目不能指望模型每轮用 `bash`/`read` 翻文件，也不能把所有设定塞进 prompt。数据层的目标是：**结构化保存 + 可被工具快速检索 + 返回模型可直接使用的权威摘要。**

## 核心原则

1. **数据文件是权威来源**：世界观、NPC、地点、怪物、DLC、物价表等进 `data/*.json`。
2. **查询工具是唯一入口**：GM 需要设定时调用 `lookup` / `lookup_location` / `get_dlc_info` 等；不要让运行时依赖 `bash`/`read`。
3. **索引与正文分离**：大数据集先查索引，按需返回正文，避免每轮塞大 JSON。
4. **返回内容面向模型**：`content` 里放权威 JSON/Markdown 摘要；`details` 只给 TUI、日志、hooks 使用。
5. **查询工具 description 必须强**：写清“必须调用场景”和“严禁凭记忆编造”。

## 推荐目录

```txt
data/
├── locations.json
├── characters.json
├── factions.json
├── monsters.json
├── items.json
├── game_rules.json
├── dlc_content.json
└── index.json              # 名称/关键词 → 文件 + key + 摘要
```

数据量很大时按领域拆索引：

```txt
data/location_index.json
data/npc_index.json
data/dlc_index.json
```

索引用脚本从正文生成，不要手写。索引条目至少包含：

```json
{
  "name": "瓦伦蒂亚",
  "aliases": ["炼金术师之城"],
  "type": "location",
  "source": "基干",
  "path": "locations.json#/瓦伦蒂亚",
  "summary": "以炼金术师公会闻名的城市……"
}
```

## 查询工具设计

### 统一 lookup（推荐）

对于中小型卡，优先做一个统一 `lookup`：

```typescript
lookup({ query: string, type?: "location" | "npc" | "faction" | "monster" | "rule" | "dlc" })
```

优点：GM 不用在多个查询工具中犹豫；工具 description 可统一强调“预设设定唯一入口”。

### 领域工具（大型卡）

大型卡可拆：

| 工具 | 负责 |
|---|---|
| `lookup_location` | 城市/区域/建筑/路线 |
| `lookup_npc` | NPC/组织成员 |
| `lookup_rule` | 规则术语、层级、货币、战斗说明 |
| `get_dlc_info` | DLC 状态、启用模块、专属条目 |
| `lookup_item` | 装备、材料、药剂、技能模板 |

拆工具的前提是：每个工具都有清晰触发场景。否则统一 lookup 更好。

## 返回格式

模型面对的 `content` 必须完整承载机械/设定结果：

```typescript
return {
  content: [{
    type: "text",
    text: JSON.stringify({ found: true, entries, guidance }, null, 2),
  }],
  details: { entries }, // TUI 可用，但不要只把权威数据放这里
};
```

不要只在 `details` 放结构化数据；有些 provider/序列化路径只把 `content` 给模型。`details` 是展示层，不是模型事实层。

## 不要依赖 bash/read

开发阶段可以用脚本和 grep 审计原卡；运行时不应要求 GM：

```txt
用 bash 搜 data/locations.json
用 read 打开 characters.json
```

原因：

- 玩家运行时工具集可能没有 bash/read。
- bash/read 返回太长，模型很难稳定抽取。
- 文件路径是实现细节，不该进入叙事决策。
- 查询工具可以做 DLC 过滤、别名归一化、摘要裁剪和错误提示。

一句话：**给 LLM 的数据入口必须是领域工具，不是文件系统。**

## 数据生成与校验

推荐为数据层配脚本：

```txt
scripts/build-index.js       # 从 data/*.json 生成索引
scripts/test-lookup.js       # 覆盖关键词命中、DLC 过滤、空结果提示
```

`test-lookup` 至少检查：

- 每个索引 path 都能 resolve 到正文。
- 常见别名能命中。
- DLC 关闭时专属条目不可见。
- 查询无结果时返回候选建议，而不是空字符串。

## Prompt 中该放什么

GM prompt 只放查询纪律和工具速查，不放大段数据：

```md
- 进入/提及预设地点时先调用 lookup(type="location")。
- 需要 NPC 背景、组织设定、怪物能力时先调用 lookup。
- 未经 lookup 确认的预设设定不存在；可以即兴创作路人细节，但不能改写预设事实。
```

世界观正文放数据层，动态事实放 state，叙事表达交给模型。
