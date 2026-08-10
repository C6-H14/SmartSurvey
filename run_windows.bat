@echo off
rem ============================================================================
rem  SmartSurvey - Windows one-click launcher (Streamlit App)
rem
rem  Purpose: Detect Python 3.10+, create/reuse .venv, install deps, launch app.
rem  Usage:   Double-click this file, or run run_windows.bat from cmd.
rem  Note:    All console text is kept ASCII-only. UTF-8 multibyte characters in
rem           a batch file cause cmd.exe to misalign command parsing byte-by-byte
rem           (e.g. swallowing the 'e' of 'echo', or mangling 'python').
rem ============================================================================

rem Switch console code page to UTF-8 to prevent mojibake
chcp 65001 >nul
title SmartSurvey - Streamlit Launcher

echo.
echo  ============================================
echo   SmartSurvey - Windows one-click launcher
echo  ============================================
echo.

rem ---------------- 0. Locate project root ----------------
set "PROJECT_ROOT=%~dp0"
pushd "%PROJECT_ROOT%"

rem ---------------- 1. Locate Python interpreter ----------------
set "PY_CMD="

rem Prefer the py launcher if available
where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py -3"

rem Fall back to python on PATH
if not defined PY_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [X] Python not found. Install Python 3.10+ (https://python.org) and check "Add to PATH".
    goto :end
)
echo [OK] Using Python interpreter: %PY_CMD%

rem ---------------- 2. Check Python version >= 3.10 ----------------
%PY_CMD% -c "import sys; sys.exit(0) if sys.version_info >= (3, 10) else sys.exit(1)" >nul 2>nul
if errorlevel 1 (
    echo [X] Requires Python 3.10 or newer. Please upgrade and retry.
    goto :end
)

for /f "delims=" %%v in ('%PY_CMD% -c "import sys; print('%d.%d' %% sys.version_info[:2])"') do set "PY_VERSION=%%v"
echo [OK] Python version: %PY_VERSION% (satisfies 3.10+)

rem ---------------- 3. Create / reuse virtual env .venv ----------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] Creating virtual env .venv ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :venv_fail
    echo [OK] Virtual env .venv created
) else (
    echo [OK] Virtual env .venv exists, skipping creation
)

rem ---------------- 4. Install dependencies ----------------
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" goto :venv_fail

echo [..] Installing requirements.txt dependencies (first run may take a while)...
"%VENV_PYTHON%" -m pip install --upgrade pip -q
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail
echo [OK] Dependencies installed

rem ---------------- 5. Ensure data directories exist ----------------
if not exist "data\logs"         mkdir "data\logs"
if not exist "data\input_pdfs"   mkdir "data\input_pdfs"
if not exist "data\output_docs"  mkdir "data\output_docs"

rem ---------------- 6. Launch Streamlit app ----------------
echo.
echo  [..] Starting SmartSurvey (http://localhost:8501) ...
echo  Press Ctrl+C to stop the app.
echo.
python -m streamlit run main.py
goto :end

:venv_fail
echo [X] Failed to create virtual env. Check your Python installation.
goto :end

:pip_fail
echo [X] Failed to install dependencies. Check network or requirements.txt.
goto :end

:end
popd
echo.
pause