# SmartSurvey SPEC

## 1. 项目定位

SmartSurvey 是一个面向 AI4SE 期末项目的非 harness 应用类软件，目标是自动完成学术 PDF 的批量解析、结构化学术矩阵提取、证据约束审查与中文 LaTeX 学术综述全文手稿生成。

项目优先服务主用户：课程项目学生。该用户需要在做课程项目、科研选题或其他项目调研时，快速把一组论文转化为可复核、可编辑、可直接贴入 Overleaf 的中文学术综述手稿。

项目的次要用户是科研助理或实验室成员。该用户更关注批量 PDF 整理、结构化论文对比矩阵、证据追溯和结果复核。

## 2. 设计原则

### 2.1 防止空气警告和过度报警

系统不得输出空泛、无证据支撑的风险、局限或可靠性判断。例如，系统不能只输出“该方法可能存在局限”“该结果可能不可靠”等套话。

每一条风险、局限、批判性结论或研究缺口都必须至少绑定：

- `title`: 论文标题。
- `evidence_page`: PDF 物理页码。
- `evidence_quote`: 1-3 句英文原文摘录。
- `trigger_reason`: 该证据为何触发该判断。
- `confidence`: 模型对该结构化抽取的置信度。

若证据无法通过后端校验，该条结论必须被拦截，不得写入学术矩阵或最终手稿。

### 2.2 鲁棒性优先

PDF 论文来自不同出版社、学科和排版模板。系统不能依赖单一章节标题、段落编号或版面结构。对于非标准 PDF，系统必须保留按页切分的完整文本，保证主体内容不会因章节识别失败而丢失。

### 2.3 中文论文输出

最终综述手稿应当使用中文撰写，但证据摘录必须保留 PDF 中的英文原文，以便用户核查。

## 3. 目标测试方向

系统最终至少在以下三个异构方向上测试，以证明它不是只适配单一学科的模板工具：

1. 基于深度学习的工业或自动化实验室场景空间异常检测。
2. Brauer-Manin 障碍相关研究。
3. 矩阵乘法理论复杂度上限。

这些方向差异很大，因此系统必须采用“通用字段 + 领域字段”的双层学术矩阵 schema。

## 4. INVEST 用户故事

### US1: 泛化文献导入与解析

作为科研人员或学生，我希望在 UI 界面批量上传任意领域的学术 PDF，以便系统自动清洗提取其核心段落文本。

验收标准：

- 用户可以一次上传多篇 PDF。
- 系统为每篇 PDF 生成基础元数据、核心章节状态和 page slices。
- 若核心章节无法识别，系统标记为 `missing`，不得编造章节内容。
- 单篇 PDF 解析失败不得导致整个批处理任务中断。

### US2: 学术矩阵提取

作为科研人员或学生，我希望系统自动从解析后的文本中提取出核心技术指标、方法、创新点和局限性。

验收标准：

- 系统输出通用字段：`title`, `authors`, `year`, `venue`, `research_problem`, `method`, `innovation`, `limitation`, `evidence_page`, `evidence_quote`, `confidence`。
- 系统根据用户输入的综述主题生成领域字段。
- 字段缺失时标记为 `missing`，不得用猜测填充。

### US3: 证据约束审查

作为科研人员或学生，我希望系统对所有提取的局限性和风险进行页码和原文段落的强绑定验证，防止出现宽泛套话。

验收标准：

- 每条结论必须绑定 `evidence_page` 和 `evidence_quote`。
- 后端执行包含关系校验：`evidence_quote in page_text[evidence_page]`。
- 若校验失败，系统拒绝写入该条结论。
- UI 显示警告：`发现无事实根据的空气警告，已自动拦截`。

### US4: 可视化矩阵对比

作为科研人员或学生，我希望在 UI 上直观看到一个多维度对比矩阵，方便我一目了然地对比不同论文的指标。

验收标准：

- UI 显示论文级对比矩阵。
- 通用字段和领域字段分区展示。
- 风险、局限、研究缺口必须能追溯到页码和原文证据。
- 用户可以复制 Markdown 矩阵内容。

### US5: 综述全文手稿生成

作为科研人员或学生，我希望一键生成逻辑清晰、结构完整的 Markdown 预览和 LaTeX 中文学术论文全文手稿，供我后续修改并贴入 Overleaf。

验收标准：

- 网页端提供 Markdown 实时预览。
- 下载端提供 `survey_draft.tex`、`matrix_table.tex` 和 `references.bib`。
- `survey_draft.tex` 为 3000-5000 字左右的中文全文手稿。
- 手稿必须包含六个完整 `\section{...}` 章节。

## 5. PDF 解析规约

### 5.1 混合解析策略

`pdf_parser.py` 采用“标准核心章节 + 兜底页码切片”的混合解析方案。

### 5.2 核心标准章节提取

系统通过启发式正则算法尝试识别以下四类几乎必含章节：

- `Abstract`
- `Introduction`
- `Conclusion`
- `References`

若某章节无法识别，系统将该章节标记为 `missing`，并在 UI 中提示用户。系统不得根据标题或上下文编造缺失章节。

### 5.3 兜底页码切片

对于论文主干技术内容，系统采用按物理页码切分的 fallback page slices：

- 每一页保存为独立文本块。
- 每个文本块保留页码。
- 即使章节标题匹配失败，也必须保留整篇 PDF 的页面文本。
- 解析异常应被记录到该论文的错误状态，不得卡死整个批处理流程。

### 5.4 解析输出结构

单篇论文解析结果至少包含：

```json
{
  "file_name": "paper.pdf",
  "title": "missing",
  "sections": {
    "abstract": "missing",
    "introduction": "missing",
    "conclusion": "missing",
    "references": "missing"
  },
  "pages": [
    {
      "page_number": 1,
      "text": "..."
    }
  ],
  "warnings": []
}
```

## 6. 学术矩阵 schema

### 6.1 通用字段

所有方向必须输出以下通用字段：

- `title`
- `authors`
- `year`
- `venue`
- `research_problem`
- `method`
- `innovation`
- `limitation`
- `evidence_page`
- `evidence_quote`
- `confidence`

### 6.2 领域字段

系统根据用户输入的综述主题动态生成领域字段。

工业或自动化实验室空间异常检测示例：

- `sensor`
- `accuracy`
- `latency`
- `deployment_scene`
- `decision_mechanism`

矩阵乘法理论复杂度上限示例：

- `complexity_bound`
- `algorithmic_technique`
- `tensor_rank_or_border_rank`
- `theoretical_result`

Brauer-Manin 障碍示例：

- `mathematical_object`
- `obstruction_type`
- `theorem_result`
- `proof_technique`

## 7. 证据绑定与后端防伪校验

### 7.1 最小证据粒度

系统采用“页码 + 原文摘录”的可验证证据绑定方案，不采用段落编号作为第一版强制要求。

原因：

- PDF 没有原生段落标签。
- 双栏、公式、脚注和表格会破坏几何分段。
- 强制段落编号会增加解析复杂度，不符合 YAGNI 和复杂度控制原则。

### 7.2 强制字段

每一条抽取结论必须包含：

- `evidence_page`: 页码数字。
- `evidence_quote`: 1-3 句英文原文摘录。

### 7.3 Containment 校验

后端必须执行等价于以下逻辑的校验：

```python
evidence_quote in page_text[evidence_page]
```

若该校验失败：

- 判定该条结论可能为模型幻觉或空气警告。
- 拦截该条记录写入。
- UI 弹出警告：`发现无事实根据的空气警告，已自动拦截`。
- 该失败应计入调试日志，方便后续分析提示词或解析器问题。

## 8. 综述生成与导出规约

### 8.1 网页端预览

网页端以 Markdown 实时预览：

- 综述正文。
- 学术对比矩阵。
- 证据绑定信息。
- 缺失字段和被拦截的空气警告。

### 8.2 下载文件

系统提供三个下载文件：

1. `survey_draft.tex`
2. `matrix_table.tex`
3. `references.bib`

### 8.3 `survey_draft.tex`（LLM 驱动合成）

`survey_draft.tex` 是中文学术论文全文手稿，由 `core/synthesis.py` 中的 `render_survey_tex_with_llm` 通过大模型驱动生成，不再使用简单的模板填充。

格式要求：

- 使用标准 `.tex` 格式。
- 建议使用 `ctexart` 或兼容 XeLaTeX 的中文模板。
- 使用 `\section{...}`，不使用 `\chapter{...}`。
- 篇幅约 3000-5000 字。
- 内容必须可被用户复制到 Overleaf 后继续编辑。

必须包含六个章节：

```tex
\section{Abstract and Introduction}
\section{Technical Taxonomy}
\section{Systematic Review and Deep Critique}
\section{Academic Comparison Matrix}
\section{Research Gaps and Future Work}
\section{Conclusion}
```

章节内容要求：

- `Abstract and Introduction`: 说明研究背景、问题定义、综述范围和论文集合。
- `Technical Taxonomy`: 根据论文技术路线自动分类建档。
- `Systematic Review and Deep Critique`: 给出系统性评述，必须强绑定页码、公式或段落证据，避免套话。
- `Academic Comparison Matrix`: 引用或嵌入 LaTeX 三线表，对比硬指标。
- `Research Gaps and Future Work`: 针对真实部署痛点提出前瞻性方向。
- `Conclusion`: 总结主要发现、局限和后续研究价值。

### 8.4 `matrix_table.tex`

`matrix_table.tex` 使用 LaTeX `booktabs` 三线表语法：

```tex
\begin{table}[htbp]
\centering
\caption{Academic Comparison Matrix}
\begin{tabular}{llll}
\toprule
Paper & Method & Key Metric & Limitation \\
\midrule
...
\bottomrule
\end{tabular}
\end{table}
```

### 8.5 `references.bib`

`references.bib` 至少包含：

- 论文标题。
- 作者。
- 年份。
- venue 或来源。
- citation key。
- 可追溯的证据页码元信息。

## 9. 凭据安全规约

API Key 是项目核心安全考核点。系统不得要求用户把真实 API Key 写入代码仓库。

### 9.1 本地 Keyring 存储

本地运行时，系统应优先使用 Python `keyring` 库，将 API Key 存入操作系统钥匙串。

必需能力：

- 首次运行时无回显录入 API Key。
- 从系统钥匙串读取 API Key。
- 更新 API Key。
- 清除 API Key。
- 当 keyring 不可用时，给出明确错误提示，不静默降级为明文文件。

### 9.2 禁止行为

系统不得：

- 将 API Key 写入 Git。
- 在 UI、日志或报错信息中显示完整 API Key。
- 将用户 API Key 打包进 Docker 镜像。
- 在公网部署时使用开发者自己的固定 Key 替所有用户调用。

## 10. Docker 与公网部署规约

### 10.1 Dockerfile

Dockerfile 应满足：

- 基于稳定 Python 镜像。
- 安装 `requirements.txt`。
- 复制项目代码。
- 暴露 Streamlit 或 Web 服务端口。
- 使用非交互方式启动应用。
- 不复制 `.env`、本地 keyring 数据、`.venv` 或用户上传的 PDF。

### 10.2 公网部署后的 Key 配置

公网部署后，每个用户必须配置自己的 Key。

安全要求：

- 用户 Key 不应进入镜像层。
- 用户 Key 不应写入公共日志。
- 单用户本地部署可使用 OS keyring。
- 多用户公网部署不得共用同一份本地 keyring 作为所有用户的凭据存储。
- 公网部署应采用会话级或用户级加密凭据存储，并在 UI 中提供 Key 更新和清除入口。

## 11. 非目标

第一版不承诺：

- 自动从学术搜索引擎下载论文。
- 自动判断论文真实引用影响力。
- 对 PDF 进行完美段落级或句子级版面还原。
- 自动保证 LaTeX 在所有 Overleaf 模板中零修改编译。
- 替代人工学术判断和最终论文修改。

## 12. 质量与测试要求

### 12.1 必测路径

- 上传多篇 PDF。
- 解析核心章节和 page slices。
- 抽取通用字段与领域字段。
- 对每条证据运行 containment 校验。
- 拦截不包含于对应页码文本的 `evidence_quote`。
- 生成 Markdown 预览。
- 导出 `survey_draft.tex`、`matrix_table.tex`、`references.bib`。

### 12.2 TDD 核心测试点

至少覆盖：

- 章节识别失败时返回 `missing`。
- 非标准 PDF 仍保留 page slices。
- `evidence_quote in page_text[evidence_page]` 成功时允许写入。
- containment 失败时拒绝写入并返回 UI 可显示错误。
- API Key 不会出现在日志和导出文件中。

## 13. 成功标准

项目完成时，应能演示：

1. 批量上传并解析论文 PDF。
2. 对至少一个测试方向生成结构化学术矩阵。
3. 对局限、风险和研究缺口执行证据绑定校验。
4. 在 UI 中展示 Markdown 预览和矩阵。
5. 导出可复制到 Overleaf 的中文 LaTeX 全文手稿和三线表。
6. 使用 keyring 完成本地 API Key 的录入、读取、更新和清除。
7. Docker 部署方案不泄露用户 Key，并说明公网部署时的用户级 Key 配置方式。

---

## 14. LaTeX 表格自适应折行优化 (Phase 3, Task 20)

### 14.1 问题描述

当前 `matrix_table.tex` 使用 `\begin{tabular}{llll}` 固定宽度列格式。当论文标题、方法描述或局限性文本超过列宽时，Overleaf 编译会产生 `overfull \hbox` 警告，表格内容溢出页边距，严重影响可读性。

### 14.2 解决方案

将 `tabular` 替换为 `tabularx` 宏包提供的 `tabularx` 环境，使用 `X` 类型列实现自动折行。

### 14.3 技术变更

- `render_matrix_table_tex` 输出 `\begin{tabularx}{\textwidth}{XXXX}` 而非 `\begin{tabular}{llll}`。
- `render_survey_tex` 和 `build_synthesis_prompt` 的 LaTeX 导言区添加 `\usepackage{tabularx}`。
- `validate_latex_syntax` 确认 `\begin{tabularx}` 和 `\end{tabularx}` 为合法环境。

### 14.4 验收标准

- `matrix_table.tex` 必须使用 `tabularx` 环境。
- 导言区必须包含 `\usepackage{tabularx}`。
- `validate_latex_syntax` 对 `tabularx` 环境返回空错误列表。

---

## 15. Streamlit 字数档位调节器 (Phase 3, Task 21)

### 15.1 功能描述

在 Streamlit 界面中添加一个滑块控件，允许用户在启动 LLM 全文学术合成前，设定目标字数（1000-10000 字，步长 500，默认 3000）。

### 15.2 数据流

```
main.py (st.slider)
  → core/pipeline.py (generate_llm_artifacts, word_count_target 参数)
    → core/synthesis.py (render_survey_tex_with_llm, word_count_target 参数)
      → core/synthesis.py (build_synthesis_prompt, word_count_target 参数)
        → System Prompt 中动态替换 "3000-5000 Chinese characters" 为实际值
```

### 15.3 参数签名

```python
def build_synthesis_prompt(topic: str, rows: list[AcademicMatrixRow], word_count_target: int = 3000) -> str

def render_survey_tex_with_llm(topic, rows, extraction_fn, word_count_target=3000, progress_callback=None) -> str

def generate_llm_artifacts(topic, rows, extraction_fn, blocked_warnings, word_count_target=3000, progress_callback=None) -> GeneratedArtifacts
```

### 15.4 验收标准

- Streamlit 界面显示 `st.slider` 控件，范围 500-8000，步长 500。
- 选择的值通过三层调用链传递至 `build_synthesis_prompt`。
- 生成的 System Prompt 中包含用户指定的字数目标。
- 不传值时默认 3000，保持向后兼容。

---

## 16. 进度上报协议 (Phase 3, Task 18)

### 16.1 统一状态回调 (Unified State Callback)

系统采用统一的回调函数在 `pipeline.py` 与调用方之间传递批量提取进度。

### 16.2 回调签名

```python
progress_callback: Callable[[int, int, str, str], None]

# 参数说明:
#   current_idx: int   — 当前正在处理的论文索引（0-based）
#   total_papers: int  — 批处理论文总数
#   state: str         — 严格枚举值：'parsing' | 'extracting' | 'self_healing' | 'completed'
#   detail: str        — 实时的可读细节字符串（如 "Retry 2/3: Generating XML feedback prompt..."）
```

### 16.3 状态机

```
parsing  →  extracting  →  self_healing (0..N 次)  →  completed
```

### 16.4 设计原则

- **解耦**: `pipeline.py` 仅通过回调广播状态，不关心调用方如何渲染。
- **控制台模式**: 调用方通过 `print(end="\r", flush=True)` 绘制 ASCII 进度条。
- **Streamlit 模式**: 调用方同时驱动 `st.progress()` 和 `st.status()` 实现丰富 UI。
- **向后兼容**: 回调参数为可选（默认 `None`），不传回调的已有调用不受影响。

### 16.5 注入点

- `extract_with_self_healing()` — 在 LLM 调用前后注入 `extracting` 和 `self_healing` 状态。
- `scripts/run_extraction.py` — 在逐论文循环中注入 `parsing` 和 `completed` 状态。

---

## 17. LLM 驱动全文合成 (Phase 3, Task 19)

### 17.1 新模块: `core/synthesis.py`

系统引入独立的 `core/synthesis.py` 模块，负责将结构化矩阵通过 LLM 合成为完整的中文学术综述 LaTeX 手稿。

选择 `core/synthesis.py` 而非修改 `core/templates.py` 或 `core/pipeline.py` 的原因：
- `templates.py` 保持纯渲染职责，不引入 LLM 调用。
- `pipeline.py` 保持编排职责，不因 LLM 合成逻辑膨胀。
- `synthesis.py` 单一职责：LLM 驱动合成 + LaTeX 语法校验。

### 17.2 函数接口

```python
def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """
    使用 LLM 生成完整中文 LaTeX 综述手稿。

    参数:
        topic: 综述主题。
        rows: 已通过证据校验的学术矩阵行。
        extraction_fn: LLM 调用适配器（prompt → raw response）。
        progress_callback: 可选的进度回调。

    返回:
        survey_draft.tex 的完整字符串内容。
    """
```

### 17.3 系统提示词设计

`build_synthesis_prompt(topic, rows)` 在 `core/synthesis.py` 中构造，包含：

- 综述主题和论文集合。
- 所有已校验的学术矩阵行（含方法、创新点、局限性、证据页码等）。
- 强制输出约束：
  - 使用 `ctexart` 文档类。
  - 必须包含六个 `\section{...}` 章节。
  - 嵌入 `booktabs` 三线对比表。
  - 禁止输出 Markdown 代码块或解释性文字，仅返回纯 LaTeX 源码。

### 17.4 LaTeX 语法校验: 轻量栈扫描器

**更新 §8 综述生成与导出规约**：`survey_draft.tex` 的生成方式从模板填充升级为 LLM 驱动合成，但保留对输出内容的 LaTeX 语法校验。

#### 17.4.1 校验规则

系统在 `core/synthesis.py` 中实现 `validate_latex_syntax(latex_source: str) -> list[str]`，返回空列表表示语法正确。

#### 17.4.2 行内公式 `$...$` 奇偶校验

逐字符扫描，忽略 `\$` 转义序列。统计 `$` 出现次数，奇数次表示未闭合。

#### 17.4.3 展示公式 `$$...$$` 奇偶校验

同上，但针对 `$$` 双美元符号块。

#### 17.4.4 `\begin{...}` / `\end{...}` 配对校验

基于栈的扫描器：遇到 `\begin{env}` 入栈，遇到 `\end{env}` 出栈并检查环境名是否匹配。不匹配或未闭合时返回错误。

#### 17.4.5 花括号 `{...}` 平衡校验

整数计数器：遇 `{` 加一，遇 `}` 减一，忽略 `\{` 和 `\}` 转义序列。计数器不应为负或最终非零。

### 17.5 自愈环路

```python
MAX_SYNTHESIS_RETRIES = 1  # Token Budget 极小

若 validate_latex_syntax 返回错误列表，系统通过 XML 标签将错误信息反馈给 LLM，
触发最多 1 次快速重试。若重试后仍不通过，返回原始 LaTeX 源码（降级输出）。

XML 反馈格式:
<latex-validation-errors>
  <error>未闭合的行内公式: $ 符号数量为奇数。</error>
  <error>环境不匹配: \\begin{table} 被 \\end{figure} 闭合。</error>
</latex-validation-errors>
```

### 17.6 测试策略

- `validate_latex_syntax` 的单元测试：覆盖有效 LaTeX、未闭合 `$`、环境不匹配、花括号不平衡、转义符号无假阳性。
- `build_synthesis_prompt` 的单元测试：提示词包含主题、所有矩阵行和输出格式约束。
- `render_survey_tex_with_llm` 的集成测试：使用 `StatefulMockExtractor`（纯 Python，无真实 LLM），验证 LaTeX 错误触发自愈重试。

---

## 18. 后续阶段规划
### 18.1 第四阶段 (Phase 4, 可选)

- Task 22: Zotero Web API 自动文献归档集成（RIS/CSV/Better BibTeX 导出）。延后原因：属于便利性功能，不影响核心综述生成质量。

## 19. 第五阶段 (Phase 5): 多凭证管理与 Bug 修复

### 19.1 概述

Phase 5 完成四个目标：
1. **多凭证管理** — CredentialStore 从单键升级为三字段 JSON 存储（api\_key, api\_base, model\_name），支持 OS 钥匙串 ← 环境变量 ← 硬编码默认值三级回退链。
2. **Bug 修复** — 修复 3 个阻塞性学术质量 Bug（空洞内容回退、巨型英文表格、Key Metric 缺失）。
3. **日志规范** — 引入 `agent_run.log` 运行时提取日志和 `data/logs/` 日志归档架构。
4. **UI 对齐** — Streamlit 侧栏三字段凭证表单。

### 19.2 JSON 凭证存储

OS Keyring 数据结构变更:

```
旧: llm_api_key = "sk-xxxx"
新: json_credentials = '{"llm_api_key":"sk-xxx","llm_api_base":"https://...","llm_model_name":"deepseek-v4-flash"}'
```

旧格式自动检测并迁移（Migration Guard），迁移后自动清除旧条目。

### 19.3 三级回退优先级

```
1. OS Keyring (get_all())
2. 环境变量 (OPENAI_API_KEY, OPENAI_API_BASE, LLM_MODEL_NAME)
3. 硬编码默认值 (DEFAULT_API_BASE, DEFAULT_MODEL_NAME)
```

注意：`get_all()` 在空 keyring 时仍返回非空默认值（`api_base`/`model_name` 有填充），所以必须以 `has_credentials()` 门控 keyring 优先，否则环境变量回退失效。

### 19.4 Bug 修复清单

| Bug | 症状 | 根因 | 修复文件 |
|-----|------|------|---------|
| 1. 空洞内容回退 | `survey_draft.tex` 各章节仅含占位符模板文本 | `run_extraction.py` 从未调用 `generate_llm_artifacts`; 缺少 LLM 合成回退提示 | `scripts/run_extraction.py`, `core/pipeline.py`, `core/synthesis.py` |
| 2. 巨型英文表格 | 表格单元格内全英文长段落，排版溢出 | Prompt 缺少中文字数约束；表格缺少物理微缩排版 | `core/extractor.py`, `core/synthesis.py`, `core/templates.py` |
| 3. Key Metric 缺失 | Key Metric 列全显示 "missing" | Extraction prompt 缺少语义提示；domain\_fields 回退脆弱 | `core/extractor.py`, `core/templates.py` |

### 19.5 日志文件架构

运行时日志与开发日志统一存放在 `data/logs/` 目录（受版本控制，不 gitignored）：

```
data/logs/
├── Agent_log.md        # 完整备份存档（Tasks 1–789，全量会话记录）
├── Agent_log1.md       # 早期任务归档（Tasks 0–15）
├── Agent_log2.md       # 当前开发日志（Tasks 16+）
└── agent_run.log       # LLM 提取运行时日志（自动生成，追加写入）
```

`agent_run.log` 格式：

```
[2026-07-09 14:30:01] [EXTRACTION] Starting batch: 4 PDFs
[2026-07-09 14:30:05] [LLM] Paper "paper_name" → 1 row, 0 corrections
[2026-07-09 14:30:08] [LLM] Generated 4823 chars
[2026-07-09 14:30:08] [EVIDENCE] 3 rows accepted, 1 blocked
[2026-07-09 14:30:08] [FALLBACK] ⚠️ LLM synthesis returned empty, using template
```

### 19.6 第五阶段测试

- Phase 5 新增测试：11 个（7 凭证 + 4 agent）
- 全量测试：54/54 通过（Phase 4 基线为 50）

---

## 20. 第六阶段 (Phase 6): 追加升级与深度 Bug 调试

### 20.1 概述

Phase 6 完成三个目标：
1. **Task 26: 零丢失保障机制 (Zero-Drop Guarantee)** — 根治批量提取时论文被静默丢弃的致命 Bug。
2. **Task 24: 大容量字数上限与输出截断防御** — 支持最高 50,000 字目标，防御 LLM 物理输出 Token 截断导致的 LaTeX 不完整。
3. **Task 25: LaTeX 排版细节精细化微调** — 表格 Caption 置顶、摘要引言冒号分隔。

---

### 20.2 Task 26: 零丢失保障机制 (Zero-Drop Guarantee)

#### 20.2.1 问题描述

用户喂入 N 篇论文时，最终产物（`survey_draft.tex`、`matrix_table.tex`、`references.bib`）中部分论文被静默丢弃，数量少于 N。

根因分析：`core/pipeline.py` 中的 `filter_rows_by_evidence()` 采用**后置标题模糊匹配**（`_find_matching_paper`）将 LLM 提取的行与源 PDF 关联。当 `pdf_parser.py` 解析非标准 PDF 导致 `paper.title == "missing"` 时，该算法无法将 LLM 提取的真实 Title 与其关联，导致该论文的所有行在证据校验阶段被拦截并移入 `blocked` 列表，**不进入最终产物**。

#### 20.2.2 解决方案: Inline Scope Binding (进程级物理绑定)

废除后置标题模糊匹配，改为在逐论文主循环内部直接完成"提取-自愈-校验-降级"闭环。

#### 20.2.3 数据流变更

```
旧管道（有缺陷）:
  for paper in papers:
      rows ← extract_with_self_healing(paper)   # 提取阶段
  all_rows += rows
  accepted, blocked ← filter_rows_by_evidence(all_rows, papers)  # ❌ 后置标题匹配
  generate_artifacts(accepted)                   # ❌ blocked 的行被丢弃

新管道（Zero-Drop）:
  for paper in papers:
      rows ← extract_with_self_healing(paper)    # 提取
      for row in rows:
          result ← validate_evidence(row, paper.page_text_by_number())  # ✅ 直接用当前 paper
          if result.accepted or 已自愈3次:
              all_rows.append(row)                # ✅ 自愈失败也强制加入
          else:
              自愈重试 (max 3)
  generate_artifacts(all_rows)                    # ✅ 100% 出现
```

#### 20.2.4 详细规则

1. **废除 `filter_rows_by_evidence()` 中的 `_find_matching_paper()` 后置匹配逻辑。**
2. **Inline Scope Binding:** 在 `for paper in papers` 主循环内部，提取出 `row` 后，**立即**使用当前循环中的 `paper.page_text_by_number()` 进行证据包含校验，彻底消灭标题匹配失败带来的失联隐患。
3. **校验通过的行:** 保持原样加入最终列表。
4. **自愈 3 次失败的行:** 立即就地执行自适应降级，将 `limitation` 改为 `"missing (unverified)"`，并**强制加入最终列表**。
5. **最终保障:** 无论提取质量如何，最终列表的行数必须等于输入 PDF 数量（论文有错误的除外），确保 `survey_draft.tex`、`matrix_table.tex`、`references.bib` 中**一个不落**地出现所有论文。

#### 20.2.5 涉及文件

- `core/pipeline.py` — 重构：删除 `filter_rows_by_evidence()`、`_find_matching_paper()`；修改 `extract_with_self_healing()` 为 Inline Scope Binding 模式
- `core/templates.py` — 验证最终产物是否包含所有论文
- `tests/test_pipeline.py` — 新增 Zero-Drop 测试用例

#### 20.2.6 验收标准

- 输入 N 篇 PDF，最终产物中必须恰好有 N 行（解析失败且有 `paper.error` 的除外）。
- 证据校验失败的行，以 `"missing (unverified)"` 降级状态强制进入最终列表。
- 不再出现论文被静默丢弃的情况。

---

### 20.3 Task 24: 大容量字数上限支持与最大输出 Token 截断防御

#### 20.3.1 问题描述

字数控制滑块上限从 10,000 字提高到 50,000 字后，几乎所有大语言模型的单次 API 输出都有物理硬件限制（通常 4096 或 8192 Token，折合中文约 3000~6000 字）。如果使用单次 API 调用（Single-pass），输出必然被模型强行截断，生成的 LaTeX 文件会缺少 `\end{document}` 等尾部内容，导致 Overleaf 无法编译。

#### 20.3.2 设计策略: 混合方案

采用**方案 A（限制上限）+ 方案 B（分章节多阶段合成）**的混合策略：

**方案 A — UI 阈值提示：**
- 在 Streamlit 滑块上方显示物理天花板提示：`推荐上限: 8000 字（超过将触发分章节多轮合成）`。
- 当用户设定超过 8000 字时，自动切换为多阶段合成模式。

**方案 B — 分章节多阶段合成（Multi-stage Synthesis）：**
- 将 6 个 `\section{...}` 章节拆分为 6 次独立的 LLM 调用，每次生成一个章节。
- 每次调用的 System Prompt 限定当前章节的内容范围，字数目标按需分配。
- 最后将所有章节片段拼接为一个完整的 `.tex` 文件。

#### 20.3.3 数据流

```
word_count_target > 8000 ?
  ├── No  → Single-pass synthesis (当前逻辑，字数上限放宽到 8000)
  └── Yes → Multi-stage synthesis (链式历史续写流):
              ├── 代码硬编码生成导言区（含 % !TEX program = xelatex 等魔术注释）
              ├── Stage 1: 调用 LLM 生成 \section{Abstract and Introduction}
              ├── Stage 2: 传入 rows 全量数据 + Section 1 真实文本 → 续写 Section 2
              ├── Stage 3: 传入 rows 全量数据 + Sections 1-2 真实文本 → 续写 Section 3
              ├── Stage 4: 传入 rows 全量数据 + Sections 1-3 真实文本 → 续写 Section 4
              ├── Stage 5: 传入 rows 全量数据 + Sections 1-4 真实文本 → 续写 Section 5
              ├── Stage 6: 传入 rows 全量数据 + Sections 1-5 真实文本 → 续写 Section 6
              └── 代码自动追加 \end{document}
```

#### 20.3.4 链式历史续写流 (Chained Contextual Generation)

**原理：** 每次调用 LLM 生成第 N 章节时，除了传入全量 rows 矩阵 JSON 数据外，还将此前已生成的第 1 到 N-1 章节的真实 LaTeX 文本一并作为 Context 喂给大模型，确保全文风格一致、逻辑连贯。

**Prompt 约束：**
```
请仔细阅读前序已生成章节的写作风格、专业术语和上下文逻辑，
顺着上文结尾，优雅自然地续写本章节，确保全文术语一致、逻辑浑然一体，
禁止出现重复介绍。
```

**Token 成本分析：** 4 篇文献的结构化 rows JSON 体积极小（不超过 2000 Tokens），重复投喂 6 次累计成本低于 0.01 元人民币，经济可行性极高。

#### 20.3.5 导言区与结束符策略

**导言区（方法 B — 代码侧硬编码）：**
废除由大模型生成 preamble。Python 代码在拼接前硬编码生成标准导言区：

```latex
% !TEX program = xelatex
% !TEX root = survey_draft.tex
\documentclass{ctexart}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage[backend=biber,style=gb7714-2015]{biblatex}
\addbibresource{ref.bib}
\begin{document}
```

Section 1 的 Prompt 仅要求其产出 `\section{Abstract and Introduction}` 及之后的内容。

**结束符（方法 D — 代码侧自动追加）：**
Section 6 仅输出学术结论内容，Python 代码在最终拼接文件末尾自动追加 `\end{document}`。

**决策理由：** 彻底杜绝 LLM 因幻觉、语法破损或生成截断导致的 LaTeX 编译崩溃。

#### 20.3.6 涉及文件

- `main.py` — 滑块上限改为 50000，添加阈值警告提示
- `core/synthesis.py` — 新增 `render_survey_tex_multi_stage()` 分章节合成函数；
  `_build_section_prompt()` 构建带链式上下文的章节 Prompt；
  `_build_preamble()` 硬编码生成导言区
- `core/pipeline.py` — 根据 `word_count_target` 自动选择合成模式

#### 20.3.7 验收标准

- 滑块范围为 1000–50000，步长 500。
- 字数 ≤ 8000 时使用单次合成（保持向后兼容）。
- 字数 > 8000 时自动切换为分章节多阶段合成。
- 导言区由代码硬编码，包含 `% !TEX program = xelatex` 魔术注释。
- 文件末尾自动追加 `\end{document}`。
- 多阶段合成的最终 LaTeX 能通过 `validate_latex_syntax` 校验。

---

### 20.4 Task 25: LaTeX 排版细节精细化微调

#### 20.4.1 Caption 置顶

**现状：** `core/templates.py` 中 `render_matrix_table_tex` 的 `\caption{...}` 位于 `\begin{tabularx}` 之前（已置顶）。

**变更：** 确认 `\caption` 在 `\begin{tabularx}` 之前，如正确则不变，如出现问题则调整顺序为：

```latex
\begin{table}[htbp]
\centering
\caption{Academic Comparison Matrix}  % ← Caption 置顶
\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabularx}{\textwidth}{XXXX}
...
\end{tabularx}
\end{table}
```

#### 20.4.2 第一部分摘要引言冒号分隔

**现状：** 第一个章节 `\section{Abstract and Introduction}` 中，摘要和引言内容混合在一起，未做视觉分隔。

**变更：** 在 Prompt（`build_synthesis_prompt`）和模板（`render_survey_tex`）中增加分隔指令，使用规范 LaTeX 语法：

```latex
\section{Abstract and Introduction}

\noindent\textbf{摘要：}...（摘要正文）...

\par\bigskip

\noindent\textbf{引言：}...（引言正文）...
```

#### 20.4.3 涉及文件

- `core/synthesis.py` — 在 `build_synthesis_prompt` 中添加摘要引言分隔排版指令
- `core/templates.py` — 在 `render_survey_tex` 的模板内容中添加 `\noindent\textbf{摘要：}` 和 `\noindent\textbf{引言：}` 格式
- `tests/test_synthesis.py` — 新增分隔符检测测试
- `tests/test_templates.py` — 新增冒号分隔检测测试

#### 20.4.4 验收标准

- `matrix_table.tex` 中的 `\caption{...}` 位于 `\begin{tabularx}` 之前。
- 生成的 `survey_draft.tex` 中 `Abstract and Introduction` 章节包含 `\noindent\textbf{摘要：}` 和 `\noindent\textbf{引言：}` 分隔标记。

---

## 21. 第七阶段 (Phase 7): LaTeX 编译加固与学术排版优化

### 21.1 概述

Phase 7 完成五个目标：
1. **Bug 1: CJK 括号检测** — 增强 `validate_latex_syntax` 检测中文字符替代 `}` 的编译崩溃 Bug。
2. **表格居中修复** — 将 `\noindent\begin{tabularx}` 拆分为两行，恢复 `\centering` 效果。
3. **统一导言区架构 (SSOT)** — 单次合成与多阶段合成统一使用 `_build_preamble()` 硬编码导言区，剥离 LLM 生成导言区的权限；升级导言区包含 `geometry 1.8cm` 和 `amsmath`。
4. **列表化分类约束** — Prompt 强制 LLM 在列举分类时使用 `\begin{itemize}` 环境。
5. **加粗领头词冒号约束** — Prompt 强制 `\textbf{...}` 后紧跟中文冒号 `：`。

### 21.2 Bug 1: CJK 括号检测

#### 21.2.1 问题描述

大模型在生成 LaTeX 源码时产生微小但致命的格式幻觉，将右花括号 `}` 误写为中文右书名号 `》`（例如 `\subsection{核心贡献与技术谱系》`），直接导致 LaTeX 编译器崩溃。

#### 21.2.2 解决方案

在 `validate_latex_syntax()` 的花括号平衡扫描器中，当检测到未能闭合的 `{` 时，扫描附近是否存在 `》` `】` `」` 等 CJK 右符号，若有则报出具体错误。

#### 21.2.3 涉及文件

- `core/synthesis.py` — 增强 `validate_latex_syntax()` 的括号检查
- `tests/test_synthesis.py` — 新增 `test_cjk_bracket_detected()` 测试

### 21.3 表格居中修复

#### 21.3.1 问题描述

`render_matrix_table_tex()` 中 `\noindent` 与 `\begin{tabularx}` 直接粘连在同一行，导致 `\noindent` 被解析为 `tabularx` 前导的一部分，破坏 `\centering` 效果。

#### 21.3.2 解决方案

将 `\noindent` 单独放在一行，`\begin{tabularx}` 另起一行。

#### 21.3.3 涉及文件

- `core/templates.py` — 拆分 `\noindent\begin{tabularx}` 为两行

### 21.4 统一导言区架构 (SSOT)

#### 21.4.1 问题描述

单次合成路径让 LLM 生成导言区，多阶段合成路径使用硬编码导言区，造成两套排版标准不一致的风险。

#### 21.4.2 解决方案

**剥离大模型导言区生成权限：** 无论是 ≤8000 字的单次合成还是 >8000 字的多阶段合成，Prompt 一律规定「直接从 `\section{Abstract and Introduction}` 开始输出正文」。所有导言区由 `_build_preamble()` 硬编码注入。

**`_build_preamble()` 升级内容：**

```latex
% !TEX program = xelatex
% !TEX root = survey_draft.tex
\documentclass{ctexart}
\usepackage[paper=a4paper, margin=1.8cm]{geometry}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{amsmath}
\usepackage[backend=biber,style=gb7714-2015]{biblatex}
\addbibresource{references.bib}
\begin{document}
```

**`render_survey_tex_with_llm()` 升级：** 将 LLM 输出包裹在 `_build_preamble()` + `\end{document}` 之间，并剥离 LLM 可能输出的导言区残留。

#### 21.4.3 涉及文件

- `core/synthesis.py` — 升级 `_build_preamble()`；更新 `build_synthesis_prompt()`；重构 `render_survey_tex_with_llm()`
- `tests/test_synthesis.py` — 更新 mock extractor，新增导言区包裹测试

### 21.5 列表化分类约束

#### 21.5.1 问题描述

大模型生成的技术分类和共识挑战常以长段落堆叠，不易阅读。

#### 21.5.2 解决方案

在 `build_synthesis_prompt()` 和 `_build_section_prompt()` 的 Prompt 中追加约束：

```
CRITICAL: When listing technical categories, consensus challenges, or research gaps,
you MUST use the \begin{itemize} LaTeX environment. Each category must be a separate \item.
Do NOT stack multiple categories in one long sentence paragraph.
```

### 21.6 加粗领头词冒号约束

#### 21.6.1 问题描述

加粗领头词 `\textbf{...}` 后缺少标点，导致文字粘连。

#### 21.6.2 解决方案

在 `build_synthesis_prompt()` 和 `_build_section_prompt()` 的 Prompt 中追加约束：

```
CRITICAL: When using \textbf{...} for a bold leading term, you MUST immediately follow
the closing brace with a Chinese colon ：.
Example: \textbf{第一类：}[explanation] — NOT \textbf{第一类}[explanation]
```

### 21.7 涉及文件汇总

| 文件 | 变更 |
|------|------|
| `core/synthesis.py` | CJK 括号检测、preamble 升级、Prompt 统一、itemize 约束、冒号约束 |
| `core/templates.py` | `\noindent` 分行 |
| `tests/test_synthesis.py` | 新增 CJK 括号测试、preamble 包裹测试、itemize 约束测试、冒号约束测试 |
| `tests/test_templates.py` | 更新表格居中测试 |

---

## 22. 第八阶段 (Phase 8): RAG 思维链泄漏清洗与格式加固

### 22.1 概述

Phase 8 完成五项硬性规约的落地，目标是让 `survey_draft.tex` 达到可直接提交学术教授审阅的 A 档质量。

### 22.2 RAG 思维链/检索标记清洗规约

#### 22.2.1 问题描述

大模型在生成正文时泄漏内部 RAG 检索标记，如 `(evidence_page=2)` 等键名残留在最终手稿中，严重破坏学术严谨性。

#### 22.2.2 解决方案

双重保险防线：

**第一道防线（Prompt 层）：** 在 `build_synthesis_prompt()` 和 `_build_section_prompt()` 中追加强制约束，严禁 LLM 在正文中输出 `evidence_page=` 等内部键名，必须使用学术界标准引用格式（如 `[1]`, `[2]`）。

**第二道防线（物理拦截层）：** 在 `core/synthesis.py` 的 `render_survey_tex_with_llm()` 和 `render_survey_tex_multi_stage()` 输出端，编写 Python 正则后处理器，使用正则 `\(evidence_page=[^\)]+\)` 彻底将此类泄漏字符物理清洗掉。

#### 22.2.3 涉及文件

- `core/synthesis.py` — Prompt 追加约束 + 正则后处理器
- `tests/test_synthesis.py` — 新增泄漏检测测试

### 22.3 硬核 LaTeX 数学公式支撑规约

#### 22.3.1 问题描述

综述手稿缺乏硬核数学公式支撑，误差度量等核心论证仅靠文字描述，学术深度不足。

#### 22.3.2 解决方案

在 extractor 提示词 (`build_extraction_prompt`) 与 synthesis 提示词 (`build_synthesis_prompt`, `_build_section_prompt`) 中追加规则：
- 要求大模型在提取和学术论述时，必须强制抓取并使用标准 LaTeX 行内/行间数学公式（如 `$E(u) = \int_\Omega |\nabla u|^2 dx$` 等物理/数学测度公式）
- 对核心误差度量展开硬核学术论证，而非仅用文字描述

#### 22.3.3 涉及文件

- `core/extractor.py` — 提取提示词追加数学公式约束
- `core/synthesis.py` — 合成提示词追加数学公式约束
- `tests/test_extractor.py` — 新增数学公式约束测试
- `tests/test_synthesis.py` — 新增数学公式约束测试

### 22.4 LaTeX 排版美学细节规约

#### 22.4.1 问题描述

手稿排版存在以下细节问题：
1. 页边距不一致
2. 摘要引言未物理分段
3. 分类用长句堆叠而非列表
4. 加粗领头词冒号在花括号外部导致视觉落差
5. 右花括号 `}` 偶尔被误写为中文右书名号 `》`

#### 22.4.2 解决方案

| # | 规约 | 实现方式 | 状态 |
|:-:|:-----|:---------|:----:|
| 1 | 页边距 `margin=1.8cm` | `_build_preamble()` 中 `geometry` 宏包 | ✅ Phase 7 |
| 2 | 摘要引言物理分段 | `\noindent\textbf{摘要：}...\par\bigskip\noindent\textbf{引言：}` | ✅ Phase 7 |
| 3 | 列表化分类 | `\begin{itemize}` 环境 + 独立 `\item` | ✅ Phase 7 |
| 4 | 加粗冒号包裹 | `\textbf{...：}` 冒号在花括号内 | ✅ Phase 7 |
| 5 | 括号笔误硬卡控 | `validate_latex_syntax()` CJK 检测 | ✅ Phase 7 |

以上规约已在 Phase 7 中通过 `SECTION_TEMPLATES` 注册表全部实现，此处归档确认。

### 22.5 100% 零丢失保证规约 (Zero-Drop Guarantee)

#### 22.5.1 问题描述

旧版 `filter_rows_by_evidence()` 使用后置标题模糊匹配，导致部分论文因标题匹配失败而被静默吞掉，违背"输入多少篇 PDF，输出就必须有多少行"的硬性要求。

#### 22.5.2 解决方案

彻底废除后置匹配过滤。在 `core/pipeline.py` 的 `extract_with_self_healing()` 主循环内部，直接进行"提取-自愈-校验-就地降级"的物理闭环：

- 每篇论文独立提取
- 证据校验不通过时，通过 `_apply_degradation()` 将 limitation 标记为 `"missing (unverified)"`，evidence_quote 标记为 `"unverified"`
- 所有论文（包括降级后的论文）均保留在最终输出中
- 在 `scripts/run_extraction.py` 中追加终极兜底：若 JSON 提取经全部重试后仍为空，使用文件名创建降级行

#### 22.5.3 涉及文件

- `core/pipeline.py` — 废除 `filter_rows_by_evidence()`，`extract_with_self_healing()` 内联零丢失
- `scripts/run_extraction.py` — 终极文件名兜底降级
- `tests/test_pipeline.py` — 新增零丢失测试（单篇降级 + 三篇场景）

### 22.6 测试用例去硬编码规约

#### 22.6.1 问题描述

全量测试用例中仍存在多处硬编码的 `"industrial automation lab..."` 旧版主题，导致测试用例不洁净、不易维护。

#### 22.6.2 解决方案

逐一检查 `tests/` 目录下的所有测试文件，将遗留的硬编码工业主题字符串替换为通用的学术中性测试字符串：

| 文件 | 行号 | 旧值 | 新值 |
|:----|:----|:-----|:-----|
| `tests/test_templates.py` | 35, 43, 78 | `"industrial anomaly detection"` | `"test topic"` |
| `tests/test_extractor.py` | 6 | `"industrial anomaly detection"` | `"test topic"` |

#### 22.6.3 涉及文件

- `tests/test_templates.py` — 清洗硬编码主题
- `tests/test_extractor.py` — 清洗硬编码主题
