# 迁移后维护

迁移只是起点。可玩版本通常靠下场测试后反复改 prompt、engine、data、tool description。

## 目录

```txt
my-card/
├── .git/                 # 建议启用
├── .pi/settings.json     # 项目包
├── agents/gm.md          # 最常改
├── data/*.json
├── engine/*.ts
├── tools/registry.ts
├── extension.ts
├── start.sh
├── sessions/             # 不进 git
└── state/                # debug export，不进 git
```

## 工作流

```txt
改代码 → ./start.sh 下场玩 → 不满意继续改 → 满意 commit
```

建议：

- 下场前 commit，方便区分代码和游玩产物。
- `sessions/` 是会话/存档，不进 git。
- `state/` 不是真相源，不进 git。
- 每张卡独立目录，别共享 sessions。

## State 心智

真相源：pi session custom entry。

```txt
session snapshot → in-memory state → state/state.json(debug)
```

规则：

- 切 session/tree/fork 后，从当前分支最近快照恢复。
- `state/state.json` 只给人看，或做旧存档导入。
- 老存档先 migration，再继续玩。
- 不要运行时长期兼容旧字段。

## .gitignore

```gitignore
node_modules/
dist/
sessions/
state/
.pi/agent/
.pi/npm/
meta/     # 仅死亡循环/跨周目永久记忆需要
```

## 常见改动

### 改 GM prompt

改 `agents/gm.md`，重启或继续下一轮即可。不需要迁移 state。

### 改 engine

改 `engine/*.ts` 后重启 pi。找干净节点重测，避免旧结果污染判断。

### 加工具 / 改 description

重启 pi，并主动触发一次。确认模型真的看到新工具。

### 改 state schema

1. bump schemaVersion
2. 写 deterministic migration
3. 加 fixture/test
4. 用 debug/setup toolset 执行迁移

不要让 runtime 同时猜新旧字段。

## 重新跑 skill

大改时可以再跑 tavern2agent。明确告诉 agent：

> 目标目录已有迁移产物和手改内容，请增量更新，不要全量覆盖。

推荐先开分支：

```bash
git checkout -b skill-rerun
git add -A && git commit -m "wip before rerun"
```

不满意就切回原分支。

## 分支

- `main`：稳定可玩
- `dev`：当前调试
- `experiment/<feature>`：大改
- `tune/<model>`：模型特化 prompt

## 禁区

- 跑游戏中手改 `state/state.json`
- 把 `state/` 加回 git
- 跨项目共享 `sessions/`
- 发布 `.pi/agent/auth.json`、`sessions/`、`state/`
