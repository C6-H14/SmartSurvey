# SmartSurvey

SmartSurvey is an AI4SE non-harness application for evidence-bound academic literature review generation.

## Features

- Batch PDF parsing with core section detection and fallback page slices.
- Two-layer academic matrix schema.
- Evidence containment validation before writing limitations or risks.
- Markdown preview and LaTeX/BibTeX exports.
- OS keyring API key storage.

## 目录结构（Directory Structure）

```text
SmartSurvey/
├── main.py                  # Streamlit 应用入口（UI 编排 + 凭据录入）
├── core/                    # 核心业务模块（职责分离，各自可单测）
│   ├── models.py            # 领域数据模型（dataclass）
│   ├── pdf_parser.py        # PDF 解析（PyMuPDF + 章节识别 + 兜底页码切片）
│   ├── extractor.py         # 学术矩阵提取 + 自愈重试
│   ├── evidence.py          # 证据归一化与 containment 校验
│   ├── schema.py            # 通用/领域 schema 生成
│   ├── credentials.py       # OS keyring 凭据存储（主后端，无头环境降级）
│   ├── synthesis.py         # LLM 综述合成 + LaTeX 校验 + 自愈编译
│   ├── templates.py         # LaTeX/BibTeX 模板与导言区（SSOT）
│   ├── graph.py             # PyVis 2D 知识图谱
│   ├── pipeline.py          # 批处理流水线（解析→提取→审查→生成）
│   └── agent.py             # LLM adapter（OpenAI 兼容，三级凭据回退）
├── tests/                   # pytest 测试（test_evidence / pipeline / schema / credentials / graph ...）
├── scripts/                 # CLI：fetch_vault.py（ArXiv 收割）、run_extraction.py、sandbox 工具
├── data/
│   ├── logs/                # Agent_log*.md 工程日志 + agent_run.log
│   ├── input_pdfs/          # 待解析 PDF（.gitignore，不入库）
│   ├── output_docs/         # 生成产物（.gitignore，不入库）
│   └── vault_100_lab_anomaly.json   # 知识图谱文献库（随仓库提供）
├── lib/                     # 前端静态资源（vis.js 知识图谱渲染等）
├── Dockerfile               # 容器分发（python:3.11-slim）
├── .gitlab-ci.yml           # CI（unit-test job，push 自动跑测试）
├── setup.sh / setup.ps1     # 一键安装脚本（macOS/Linux / Windows）
├── run_windows.bat          # Windows 一键启动脚本（cmd.exe）
├── requirements.txt         # Python 依赖
└── .env                     # 仅开发兼容源（见 Credential Safety）
```

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

SmartSurvey stores the LLM API key in the **operating system keyring** (primary backend, via `core/credentials.py`). The full key is never displayed in the UI, logs, exported files, Docker images, or committed source files.

Key handling guarantees:

- **Never hardcoded** into source and **never committed** to Git (checked before each commit).
- **Never written** to logs, terminal history, or plaintext config files.
- **Never echoed in full** — the UI only shows a `Configured / Missing` status; API-key input uses a masked password field.
- **Update / Clear** supported: `save_all()` overwrites on the same key; `clear_all()` removes it.
- **Headless fallback**: in containers / cloud (no OS keyring), SmartSurvey transparently degrades to session-memory storage.

> ⚠️ **`.env` 明文风险警告**: The `.env` file is **plaintext** and, when present, is loaded by the process at runtime. It is **gitignored** so it is never committed — but **any key written to `.env` exists in plaintext and is visible to the process environment**. `.env` is therefore supported **only as a development compatibility source** for `OPENAI_API_BASE` and `LLM_MODEL_NAME`. **Do NOT put a real `OPENAI_API_KEY` into `.env`** — use the keyring via the in-app credential form, or a secret store (env var injection / Secrets manager) for deployed environments.

## Known Limits

The first version does not automatically download papers, reconstruct perfect PDF paragraphs, or guarantee zero-edit LaTeX compilation in every Overleaf template.

Platform / distribution limits:

- **Docker image excludes `data/`** by design (`.dockerignore`). The knowledge-graph module reads `data/vault_100_lab_anomaly.json`, so **graph rendering is unavailable inside the container** unless that file is volume-mounted. Other features (parse / extract / synthesize / export) work normally.
- **Headless keyring**: containers and Streamlit Cloud have no OS keyring; they degrade to session-memory storage and require keys injected via environment variables / Secrets (not the local keyring).
- **`.env` is dev-only**: see Credential Safety — real keys must use the keyring or a secret store, not `.env`.
