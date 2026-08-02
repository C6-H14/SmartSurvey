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

# ---------- 1. Python 检查 ----------
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+。"
    exit 1
fi
echo "✅ 检测到 Python: $(command -v python3)"

# ---------- 2. 创建虚拟环境 ----------
if [ ! -d ".venv" ]; then
    echo "📦 正在创建虚拟环境 .venv ..."
    python3 -m venv .venv
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境 .venv 已存在，跳过创建"
fi

# ---------- 3. 激活虚拟环境并安装依赖 ----------
echo "📦 正在安装 requirements.txt 依赖 ..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt
echo "✅ 依赖安装完成"

# ---------- 4. 建立 data/ 目录 ----------
mkdir -p data/input_pdfs data/logs data/output_docs
echo "✅ data/ 目录结构已就绪"

# ---------- 5. 完成 ----------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        SmartSurvey 安装完成！ 🎉             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "启动应用: source .venv/bin/activate && streamlit run main.py"
echo "抓取文献: source .venv/bin/activate && python3 scripts/fetch_vault.py --topic '3D anomaly detection' --limit 100"