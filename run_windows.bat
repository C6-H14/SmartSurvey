@echo off
rem ============================================================================
rem  SmartSurvey - Windows 一键启动脚本 (Streamlit App)
rem
rem  用途: 自动检测 Python 3.10+、创建/复用 .venv、安装依赖并启动应用。
rem  用法: 双击本文件，或在 cmd 中执行 run_windows.bat
rem  说明: chcp 65001 将控制台切换为 UTF-8 编码，杜绝中文/英文混排乱码。
rem ============================================================================

rem 切换控制台编码为 UTF-8，杜绝终端乱码
chcp 65001 >nul
title SmartSurvey - Streamlit Launcher

echo.
echo  ============================================
echo   SmartSurvey - Windows 一键启动脚本
echo  ============================================
echo.

rem ---------------- 0. 定位项目根目录 ----------------
set "PROJECT_ROOT=%~dp0"
pushd "%PROJECT_ROOT%"

rem ---------------- 1. 定位 Python 解释器 ----------------
set "PY_CMD="

rem 优先使用 py launcher（若存在）
where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py -3"

rem 否则回退到 PATH 中的 python
if not defined PY_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [X] 未找到 Python。请先安装 Python 3.10+（https://python.org），并勾选 "Add to PATH"。
    goto :end
)
echo [OK] 使用 Python 解释器: %PY_CMD%

rem ---------------- 2. 校验 Python 版本 >= 3.10 ----------------
%PY_CMD% -c "import sys; sys.exit(0) if sys.version_info >= (3, 10) else sys.exit(1)" >nul 2>nul
if errorlevel 1 (
    echo [X] 需要 Python 3.10 或更高版本，当前版本过低。请升级后重试。
    goto :end
)

for /f "delims=" %%v in ('%PY_CMD% -c "import sys; print('%d.%d' %% sys.version_info[:2])"') do set "PY_VERSION=%%v"
echo [OK] Python 版本: %PY_VERSION% (满足 3.10+)

rem ---------------- 3. 创建 / 复用虚拟环境 .venv ----------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] 正在创建虚拟环境 .venv ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :venv_fail
    echo [OK] 虚拟环境 .venv 已创建
) else (
    echo [OK] 虚拟环境 .venv 已存在，跳过创建
)

rem ---------------- 4. 激活虚拟环境并安装依赖 ----------------
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" goto :venv_fail

echo [..] 安装 requirements.txt 依赖（首次运行需等待）...
"%VENV_PYTHON%" -m pip install --upgrade pip -q
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail
echo [OK] 依赖安装完成

rem ---------------- 5. 确保 data 目录存在 ----------------
if not exist "data\logs"         mkdir "data\logs"
if not exist "data\input_pdfs"   mkdir "data\input_pdfs"
if not exist "data\output_docs"  mkdir "data\output_docs"

rem ---------------- 6. 启动 Streamlit 应用 ----------------
echo.
echo  [..] 启动 SmartSurvey (http://localhost:8501) ...
echo  按 Ctrl+C 可停止应用。
echo.
"%VENV_PYTHON%" -m streamlit run main.py
goto :end

:venv_fail
echo [X] 虚拟环境创建失败，请检查 Python 安装。
goto :end

:pip_fail
echo [X] 依赖安装失败，请检查网络或 requirements.txt。
goto :end

:end
popd
echo.
pause