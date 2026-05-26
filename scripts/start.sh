#!/usr/bin/env bash
# 启动脚本 —— 在转换产出的项目目录中运行
# 自动检测 pi、加载 extension.ts 并进入游戏，支持透传参数（如 --model）
set -euo pipefail

if ! command -v pi &>/dev/null; then
  echo "错误: pi 未安装，请先安装 pi coding agent" >&2
  echo "安装指引: https://github.com/earendil-works/pi-coding-agent" >&2
  exit 1
fi

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$(readlink -f "$0")")"

echo "启动《$(basename "$PWD")》..."
# 会话存档放在项目内，方便打包带走；发布前删除 sessions/。
mkdir -p ./sessions

# state/ 是 session-backed 状态的 debug export / legacy fallback，真实存档在 pi session 快照中。
# 生成项目时应把 state/ 写进 .gitignore；发布包不要包含 state/。

# ---- 项目隔离 ----
# PI_CODING_AGENT_DIR 将 pi 的配置目录从 ~/.pi/agent/ 切换到 .pi/agent/，
# 实现全局配置/skills 的隔离。项目自己的 extension.ts 通过 -e 显式加载。
#
# --no-skills 禁用所有自动发现的 skill（全局、npm 包内置等），
# 然后 --skill ./skills/ 显式加载项目自己的 skills 目录。
# 确保 reviewer/coder/oracle 等开发用 skill 不会泄漏到游戏会话中。
#
# 项目级 pi 包（例如 npm:pi-subagents / npm:pi-powerline-footer）应声明在
# 项目根 .pi/settings.json 的 packages 数组中；pi 首次启动会自动安装到 .pi/npm/。
# 发布包保留 .pi/settings.json 和 .pi/agents/，不要打包 .pi/npm/。
#
# 首次启动时自动初始化 .pi/agent/：
#   1. 如有全局 auth，复制过来（也可在后续手动 /login）
#   2. 创建最小 settings.json

mkdir -p .pi/agent

if [ ! -f .pi/agent/auth.json ] && [ -f "$HOME/.pi/agent/auth.json" ]; then
  cp "$HOME/.pi/agent/auth.json" .pi/agent/auth.json
  echo "✓ 已复制认证信息到项目隔离环境"
fi

if [ ! -f .pi/agent/settings.json ]; then
  cat > .pi/agent/settings.json <<-'EOF'
{
  "theme": "dark"
}
EOF
  echo "✓ 已创建项目隔离配置 (.pi/agent/settings.json)"
  echo "  （如需指定默认模型，编辑此文件添加 defaultProvider / defaultModel）"
fi

# 普通玩家模式禁用 pi-subagents 内置 coding agents，避免 reviewer/worker/oracle 等出现在游戏运行时。
# 开发时如需保留内置 agents：TAVERN2AGENT_DEV=1 ./start.sh
node - <<'NODE'
const fs = require('fs');
const path = '.pi/agent/settings.json';
const dev = process.env.TAVERN2AGENT_DEV === '1';
let settings = {};
try {
  if (fs.existsSync(path)) settings = JSON.parse(fs.readFileSync(path, 'utf8'));
} catch {
  settings = {};
}
settings.theme ??= 'dark';
settings.subagents ??= {};
settings.subagents.disableBuiltins = !dev;
fs.writeFileSync(path, JSON.stringify(settings, null, 2) + '\n');
NODE
if [ "${TAVERN2AGENT_DEV:-}" = "1" ]; then
  echo "✓ 开发模式：保留 pi-subagents 内置 agents"
else
  echo "✓ 玩家模式：已禁用 pi-subagents 内置 coding agents（开发模式: TAVERN2AGENT_DEV=1 ./start.sh）"
fi

export PI_CODING_AGENT_DIR=".pi/agent"

# 记录 pi 退出码，但保证提示始终显示
pi_exit=0
pi \
  --no-skills \
  --skill ./skills/ \
  -e ./extension.ts \
  --session-dir ./sessions \
  --no-context-files \
  "$@" || pi_exit=$?

cat <<'MSG'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  提示：如要分享此项目（git push / 打包发送等），
    请删除 .pi/agent/auth.json（包含 API 密钥）、sessions/（会话存档）和 state/（调试导出）。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MSG
exit $pi_exit
