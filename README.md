# SmartSurvey

SmartSurvey is an AI4SE non-harness application for evidence-bound academic literature review generation.

## Features

- Batch PDF parsing with core section detection and fallback page slices.
- Two-layer academic matrix schema.
- Evidence containment validation before writing limitations or risks.
- Markdown preview and LaTeX/BibTeX exports.
- OS keyring API key storage.

## 前置要求（Prerequisites）

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| **Python** | **3.10 及以上** | 安装时勾选 "Add to PATH"（Windows） |
| 操作系统 | Windows / macOS / Linux | 无特殊依赖 |
| 内存 | ≥ 4 GB 建议 | LLM 合成阶段较吃内存 |

> 💡 **Linux (Debian/Ubuntu)**：若缺少 `venv` 模块，请先执行
> `sudo apt-get install -y python3-venv python3-pip`。三个安装脚本（
> `setup.ps1` / `setup.sh` / `run_windows.bat`）均会**自动校验 Python ≥ 3.10**，
> 版本过低会直接提示并终止。

## 安装（Install）

### 一键安装（推荐，自动校验 Python 3.10+ 并装好依赖）

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
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 验证安装是否成功（自检）

```bash
# 检查依赖是否完整且无冲突
python -m pip check

# 运行测试（应全部通过）
python -m pytest tests -v
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

## Streamlit Community Cloud 部署

本项目已针对 Streamlit Cloud 无头容器做过加固（keyring 会话级降级、图谱内存渲染、不暴露容器路径）。部署步骤：

1. 将代码推送到 GitHub 仓库（本仓库 `main` 分支）。
2. 在 [share.streamlit.io](https://share.streamlit.io) 登录，点击 **New app**，选择仓库与分支，主入口选择 `main.py`。
3. 点击 **Deploy**。容器会自动安装 `requirements.txt` 并启动。
4. 访问分配的 `*.streamlit.app` 地址。

> **如何获取数据文件？** 知识图谱依赖 `data/vault_100_lab_anomaly.json`（已随仓库提供）。若要更新图谱数据，可在本地运行
> `.venv\Scripts\python -m scripts.fetch_vault` 后把新 JSON 提交到仓库再重新部署。

> **密钥注入（Streamlit Cloud）：** 在应用详情的 **Settings → Secrets** 中配置
> `OPENAI_API_BASE` / `OPENAI_API_KEY` / `LLM_MODEL_NAME`。无头容器没有桌面 Keyring，
> SmartSurvey 会自动降级到会话级内存存储，不会因此红屏。

## Credential Safety

SmartSurvey stores the LLM API key in the operating system keyring. The full key is never displayed in the UI, logs, exported files, Docker images, or committed source files.

For development compatibility, `.env` may still supply `OPENAI_API_BASE` and `LLM_MODEL_NAME` only. Do not put real API keys in `.env` or Git.

## Known Limits

The first version does not automatically download papers, reconstruct perfect PDF paragraphs, or guarantee zero-edit LaTeX compilation in every Overleaf template.
