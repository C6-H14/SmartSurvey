#!/usr/bin/env bash
# =============================================================================
#  SmartSurvey — Mac / Linux 一键安装脚本
# =============================================================================
#  自动创建虚拟环境、安装依赖、建立 data/ 目录结构。
#  用法: chmod +x setup.sh && ./setup.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║     SmartSurvey Mac/Linux 一键安装脚本       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ---------- 1. Python 3.10+ 检查 ----------
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+（https://python.org）。"
    exit 1
fi

PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info[0])' 2>/dev/null)"
PY_MINOR="$(python3 -c 'import sys; print(sys.version_info[1])' 2>/dev/null)"
if [ -z "$PY_MAJOR" ] || [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "❌ 需要 Python 3.10 或更高版本（当前 ${PY_MAJOR:-?}.${PY_MINOR:-?}）。请升级后重试。"
    exit 1
fi
echo "✅ 检测到 Python: $(command -v python3) (${PY_MAJOR}.${PY_MINOR})"

# ---------- 2. 确保 venv 模块可用（Debian/Ubuntu 常缺 python3-venv）----------
if ! python3 -c "import venv" &>/dev/null; then
    echo "❌ 缺少 Python venv 模块。Linux (Debian/Ubuntu) 请先执行:"
    echo "   sudo apt-get install -y python3-venv python3-pip"
    exit 1
fi

# ---------- 3. 创建虚拟环境 ----------
if [ ! -d ".venv" ]; then
    echo "📦 正在创建虚拟环境 .venv ..."
    python3 -m venv .venv
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境 .venv 已存在，跳过创建"
fi

# ---------- 4. 激活虚拟环境并安装依赖 ----------
echo "📦 正在安装 requirements.txt 依赖 ..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt
echo "✅ 依赖安装完成"

# ---------- 5. 建立 data/ 目录 ----------
mkdir -p data/input_pdfs data/logs data/output_docs
echo "✅ data/ 目录结构已就绪"

# ---------- 6. 完成 ----------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        SmartSurvey 安装完成！ 🎉             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "启动应用: source .venv/bin/activate && streamlit run main.py"
echo "抓取文献: source .venv/bin/activate && python3 scripts/fetch_vault.py --topic '3D anomaly detection' --limit 100"