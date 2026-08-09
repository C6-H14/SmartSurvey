<#
.SYNOPSIS
    SmartSurvey — Windows 一键安装脚本
.DESCRIPTION
    自动创建虚拟环境、安装依赖、建立 data/ 目录结构。
    用法: powershell -ExecutionPolicy Bypass -File setup.ps1
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir ".")

Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     SmartSurvey Windows 一键安装脚本        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. Python 3.10+ 检查 ----------
# 优先使用 py launcher（若存在），否则回退到 PATH 中的 python
$python = $null
$pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $python = $pyLauncher
    $pythonInvoke = "py -3"
} else {
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    $pythonInvoke = "python"
}
if (-not $python) {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.10+ 并确保其在 PATH 中。" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 检测到 Python: $($python.Source)" -ForegroundColor Green

# 校验版本 >= 3.10
$pyVersion = & $python.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
$pyOK = & $python.Source -c "import sys; sys.exit(0) if sys.version_info >= (3,10) else sys.exit(1)" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $pyVersion) {
    Write-Host "❌ 需要 Python 3.10 或更高版本（当前: $pyVersion）。请升级后重试。" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python 版本: $pyVersion（满足 3.10+）" -ForegroundColor Green

# ---------- 2. 创建虚拟环境 ----------
if (-not (Test-Path "$ProjectRoot\.venv")) {
    Write-Host "📦 正在创建虚拟环境 .venv ..." -ForegroundColor Yellow
    & $python.Source -m venv "$ProjectRoot\.venv"
    Write-Host "✅ 虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "✅ 虚拟环境 .venv 已存在，跳过创建" -ForegroundColor Green
}

# ---------- 3. 激活虚拟环境并安装依赖 ----------
$pip = "$ProjectRoot\.venv\Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    Write-Host "❌ 未找到 pip ($pip)" -ForegroundColor Red
    exit 1
}

Write-Host "📦 正在安装 requirements.txt 依赖 ..." -ForegroundColor Yellow
& $pip install --upgrade pip -q
& $pip install -r "$ProjectRoot\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ pip install 失败" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 依赖安装完成" -ForegroundColor Green

# ---------- 4. 建立 data/ 目录 ----------
$dataDirs = @(
    "data\input_pdfs",
    "data\logs",
    "data\output_docs"
)
foreach ($dir in $dataDirs) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "📁 创建目录: $dir" -ForegroundColor Yellow
    }
}
Write-Host "✅ data/ 目录结构已就绪" -ForegroundColor Green

# ---------- 5. 完成 ----------
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        SmartSurvey 安装完成！ 🎉             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动应用: .venv\Scripts\activate ; streamlit run main.py" -ForegroundColor White
Write-Host "抓取文献: .venv\Scripts\activate ; python scripts\fetch_vault.py --topic ""3D anomaly detection"" --limit 100" -ForegroundColor White