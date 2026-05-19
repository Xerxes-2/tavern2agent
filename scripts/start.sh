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
# 会话存档放在项目内，方便打包带走
mkdir -p ./sessions

# pi-rewind-hook 等回退扩展依赖 git 仓库——确保已 init（state/ 不要 .gitignore）
if [ ! -d .git ]; then
  git init -q
  echo "✓ 已初始化 git 仓库（回退扩展所需）"
fi

# ---- 项目隔离 ----
# PI_CODING_AGENT_DIR 将 pi 的配置目录从 ~/.pi/agent/ 切换到 .pi/agent/，
# 实现全局配置/skills 的隔离。项目自己的 extension.ts 通过 -e 显式加载，
# skills/ 目录通过 extension 的 resources_discover 钩子注册（见 pi-integration.md）。
#
# 项目级 pi 包（例如 npm:pi-subagents / npm:pi-rewind-hook）应声明在
# 项目根 .pi/settings.json 的 packages 数组中；pi 首次启动会自动安装到 .pi/npm/。
# 发布包保留 .pi/settings.json 和 .pi/agents/，不要打包 .pi/npm/。
#
# 首次启动时自动初始化 .pi/agent/：
#   1. 如有全局 auth，复制过来（也可在后续手动 /login）
#   2. 创建最小 settings.json
#
# 如需额外本地 extension 或 skill 文件，用 -e / --skill 显式指定。

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

export PI_CODING_AGENT_DIR=".pi/agent"

# 记录 pi 退出码，但保证提示始终显示
pi_exit=0
pi \
  -e ./extension.ts \
  --session-dir ./sessions \
  "$@" || pi_exit=$?

cat <<'MSG'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  提示：如要分享此项目（git push / 打包发送等），
   请删除 .pi/agent/auth.json（包含 API 密钥）
   否则密钥会随项目一起泄漏。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MSG
exit $pi_exit
