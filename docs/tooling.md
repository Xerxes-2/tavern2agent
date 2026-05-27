# 工具与工作流

可选工具。影响体验，不影响迁移产物本身。

## SSH + zellij

适合把游戏跑在云服务器。

优点：

- 断网/换设备后 `zellij attach` 继续
- 多窗格：游戏、state 观察、编辑器并排
- 手机 SSH 也能回合制游玩

tmux/screen 也可以。zellij 默认体验更友好。

## viddy + jq

实时看 state：

```bash
viddy -n 1 jq -C . state/state.json
viddy -d jq -C .主角.生命值 state/state.json
```

`-C` 保留颜色，`-d` 高亮变化。用于抓“嘴上扣血但 state 没动”。

## ask_user_question

```bash
pi install npm:@juicesharp/rpiv-ask-user-question
```

适合：

- 开局 setup
- 路线选择
- 重大决策
- 多选配置

可在 GM prompt 里写：重大选择用 ask_user_question 呈现。

## pi-web-access

```bash
pi install npm:pi-web-access
```

给 GM web 搜索、URL 抓取、GitHub/PDF/YouTube 能力。

适合现实题材查资料。虚构世界要在 prompt 里禁用 web，避免污染设定。

## Tau

```bash
pi install npm:tau-mirror
```

pi 的 web mirror。适合手机/浏览器继续同一 session。

## PiClaw

自托管 web 工作台，重型方案。适合展示或给非技术用户用；只想手机继续玩时优先 Tau。

## 小习惯

- 每张卡独立目录。
- `./start.sh -p "一句测试"` 快速回归。
- prompt 改动打 tag，如 `prompt-v2`。
- engine 纯函数配单元测试。
