# 脚本分析

审计两类脚本：`data.extensions.tavern_helper.scripts[]` 和 `data.extensions.regex_scripts[]`。

## tavern_helper.scripts

| 类型 | 信号 | 处理 |
|---|---|---|
| Zod 变量结构 | `registerMvuSchema`、`z.object` | 提取 schema，辅助 `INITIAL_STATE` |
| MVU 引擎 | `MagVarUpdate` 等通用引擎 import | 丢弃；agent 用工具/engine |
| 游戏系统脚本 | 自定义 URL import | 尝试抓外链；失败则按 MVU 条目重写 |
| ST 工具类 | 世界书强制、自动更新等 | 丢弃 |
| UI 面板 | HTML/CSS/状态栏 | 丢 UI，提取字段名交叉校验 state |

快速分类：

```bash
python3 - <<'PY'
import json
card=json.load(open('card.json'))
for i,s in enumerate(card['data'].get('extensions',{}).get('tavern_helper',{}).get('scripts',[])):
    c=s.get('content','')
    kind='zod' if 'registerMvuSchema' in c else 'mvu_engine' if 'MagVarUpdate' in c else 'game' if c.startswith('import') else 'ui/other'
    print(f"[{i}] {s.get('name','?')} enabled={s.get('enabled')} kind={kind} len={len(c)}")
PY
```

提取 Zod：

```bash
python3 - <<'PY'
import json,re
card=json.load(open('card.json'))
for s in card['data'].get('extensions',{}).get('tavern_helper',{}).get('scripts',[]):
    c=s.get('content','')
    if 'registerMvuSchema' in c:
        c=re.sub(r'^import.*?;\s*','',c)
        c=re.sub(r'\$\(.*registerMvuSchema.*\n*$','',c,flags=re.S)
        open('/tmp/schema_extracted.ts','w').write(c)
        print(c[:2000])
PY
```

外链脚本：

```bash
curl -sL '<URL>' | head -100
```

抓不到时，从 `[mvu_plot]` / `[mvu_update]` 推规则。

## regex_scripts

| 类型 | 信号 | 处理 |
|---|---|---|
| 变量清理 | `UpdateVariable` | 丢弃 |
| AI 隐藏 | `StatusPlaceHolder` 且 replace 空 | 丢弃 |
| UI 状态面板 | 大段 HTML/CSS | 丢 UI，提取字段 |
| 游戏内容注入 | replace 内有 JSON/棋子/规则 | 提取到 data/engine |

快速分类：

```bash
python3 - <<'PY'
import json
card=json.load(open('card.json'))
for i,rs in enumerate(card['data'].get('extensions',{}).get('regex_scripts',[])):
    find=rs.get('findRegex','')
    repl=rs.get('replaceString','')
    if 'UpdateVariable' in find: kind='ST_CLEANUP'
    elif 'StatusPlaceHolder' in find and not repl: kind='AI_HIDE'
    elif len(repl)>5000: kind='UI_PANEL'
    elif len(repl)>500: kind='GAME_INJECT'
    else: kind='OTHER'
    print(f"[{i}] {rs.get('scriptName','?')}: {kind} repl={len(repl)}B")
PY
```
