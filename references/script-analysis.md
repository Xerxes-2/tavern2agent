# 卡内脚本分析

MVU 角色卡携带两类脚本：`tavern_helper.scripts` 和 `regex_scripts`。

## tavern_helper.scripts（MVU 助手脚本）

位于 `data.extensions.tavern_helper.scripts[]`。在酒馆客户端运行。迁移时按类型处理：

| 脚本类型 | 识别特征 | 迁移方式 |
|---------|---------|---------|
| **Zod 变量结构** | content 含 `registerMvuSchema` + `z.object({…})` | 提取 `export const Schema`，去掉首尾酒馆注册代码。用于理解数据模型、生成 `INITIAL_STATE` 结构 |
| **MVU 引擎** | content 是 `import '…MagVarUpdate…'` | **丢弃**。agent 用 `get_status`/`patch_state`/`dispatch` 工具替代 |
| **游戏系统脚本** | content 是 `import '…性斗学园脚本…'` 等自定义 URL | 外链脚本不在卡 JSON 内。① 读 MVU 条目中的公式/规则 ② 尝试 `curl` 抓取 ③ 抓不到则从 MVU 条目推断 engine 模块 |
| **ST 工具类** | content 是 `import '…世界书强制…'` / `import '…自动更新…'` | **丢弃**。ST 客户端能力，agent 不需要 |
| **UI 悬浮窗** | content 是 HTML/CSS/JS 状态面板 | **丢弃 UI 代码**，但提取状态字段名作为 `INITIAL_STATE` 交叉校验 |

### 探索命令

```bash
# 列出所有脚本及其类型
python3 -c "
import json
with open('card.json') as f: card = json.load(f)
scripts = card['data']['extensions']['tavern_helper']['scripts']
for i, s in enumerate(scripts):
    name = s.get('name', '?')
    enabled = s.get('enabled', False)
    content = s.get('content', '')
    kind = 'zod' if 'registerMvuSchema' in content else ('mvu_engine' if 'MagVarUpdate' in content else ('game' if content.startswith('import') else 'ui/other'))
    print(f'[{i}] {name} enabled={enabled} kind={kind} len={len(content)}')
"

# Zod 脚本 → 提取 schema
python3 -c "
import json, re
with open('card.json') as f: card = json.load(f)
for s in card['data']['extensions']['tavern_helper']['scripts']:
    if 'registerMvuSchema' in s.get('content', ''):
        c = s['content']
        c = re.sub(r'^import.*?;\\s*', '', c)
        c = re.sub(r'\\$\\(.*registerMvuSchema.*\\n*$', '', c, flags=re.DOTALL)
        print(c)
        with open('/tmp/schema_extracted.ts', 'w') as f: f.write(c)
"

# 游戏系统脚本 → 尝试抓取外链
curl -sL '<脚本中的URL>' 2>&1 | head -100
```

> 如果抓不到外链代码，MVU 条目（`[mvu_plot]`/`[mvu_update]`）中通常已写清核心公式，用 engine 模块重新实现即可。

## regex_scripts

位于 `data.extensions.regex_scripts[]`。ST 的正则替换脚本，在消息渲染前后执行。

| 类型 | 识别特征 | 迁移方式 |
|------|---------|---------|
| **变量提取/清除** | findRegex 匹配 `<UpdateVariable>` | **丢弃**。agent 不输出 UpdateVariable 标签 |
| **AI 隐藏** | findRegex 匹配 `<StatusPlaceHolderImpl/>`，replace 为空 | **丢弃**。agent 不需要向 AI 隐藏状态栏 |
| **UI 状态面板** | replaceString 是大量 HTML/CSS（≥5KB） | **丢弃 HTML**，但提取状态字段名列表作为 `INITIAL_STATE` 交叉校验 |
| **游戏内容注入** | replaceString 含游戏数据/JSON/棋子配置 | **提取逻辑**。HTML 中内嵌了游戏状态数据，提取数据结构转化为 engine 或 data 文件 |

### 探索命令

```bash
# 快速分类所有 regex_scripts
python3 -c "
import json
with open('card.json') as f: card = json.load(f)
for i, rs in enumerate(card['data']['extensions'].get('regex_scripts', [])):
    name = rs.get('scriptName', '?')
    find = rs.get('findRegex', '')[:80]
    repl_len = len(rs.get('replaceString', ''))
    if 'UpdateVariable' in find: kind = 'ST_CLEANUP'
    elif 'StatusPlaceHolder' in find and repl_len == 0: kind = 'AI_HIDE'
    elif repl_len > 5000: kind = 'UI_PANEL'
    elif repl_len > 500: kind = 'GAME_INJECT'
    else: kind = 'OTHER'
    print(f'[{i}] {name}: {kind} (repl={repl_len}B)')
"
```
