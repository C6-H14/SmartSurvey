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

### 8.3 `survey_draft.tex`

`survey_draft.tex` 是中文学术论文全文手稿，不是空泛草稿。

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
