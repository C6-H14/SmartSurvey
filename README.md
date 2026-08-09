# SmartSurvey

SmartSurvey is an AI4SE non-harness application for evidence-bound academic literature review generation.

## Features

- Batch PDF parsing with core section detection and fallback page slices.
- Two-layer academic matrix schema.
- Evidence containment validation before writing limitations or risks.
- Markdown preview and LaTeX/BibTeX exports.
- OS keyring API key storage.

## Install

### 一键安装（推荐）

**Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**macOS / Linux:**

```bash
chmod +x setup.sh && ./setup.sh
```

### 手动安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run（本地运行）

```bash
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
streamlit run main.py
```

打开浏览器访问 <http://localhost:8501> 即可使用。

## Windows 一键分发（run_windows.bat）

Windows 用户可直接双击 `run_windows.bat`，脚本会自动完成：

1. **检测 Python 3.10+**（优先 `py` launcher，回退 `PATH` 中的 `python`）。
2. **创建 / 复用虚拟环境** `.venv`。
3. **安装依赖** `requirements.txt`。
4. **确保 `data/` 目录就绪**，然后启动 `streamlit run main.py`。

```bat
run_windows.bat
```

> 💡 脚本开头已执行 `chcp 65001` 将控制台切换为 UTF-8 编码，可杜绝 Windows 终端的中文/英文混排乱码。首次运行会联网安装依赖，耗时较长属正常现象。

也可以在 cmd / PowerShell 中以开发模式手动启动：

```bash
.venv\Scripts\activate
streamlit run main.py --server.headless false
```

## Test

```bash
python -m pytest tests -v
```

## Docker 部署

Dockerfile 基于 `python:3.11-slim`，暴露 8501 端口并内置健康检查。

```bash
# 构建镜像
docker build -t smartsurvey:local .

# 运行容器（映射 8501 端口）
docker run --rm -p 8501:8501 smartsurvey:local

# 确认运行状态
curl http://localhost:8501/_stcore/health   # 返回 "ok" 即正常
```

> ⚠️ 密钥安全：请勿把真实 API Key 写入镜像或 `.env`。生产环境建议通过容器环境变量注入，SmartSurvey 会将其存入会话级内存回退存储。

## Credential Safety

SmartSurvey stores the LLM API key in the operating system keyring. The full key is never displayed in the UI, logs, exported files, Docker images, or committed source files.

For development compatibility, `.env` may still supply `OPENAI_API_BASE` and `LLM_MODEL_NAME` only. Do not put real API keys in `.env` or Git.

## Known Limits

The first version does not automatically download papers, reconstruct perfect PDF paragraphs, or guarantee zero-edit LaTeX compilation in every Overleaf template.
