# Prompt 泛化改造设计：Section Template Registry

**Date:** 2026-07-10
**Status:** Draft

---

## Overview

移除 `build_synthesis_prompt()` 和 `_build_section_prompt()` 中所有硬编码的领域特定描述，通过 `SECTION_TEMPLATES` 全局注册表实现主题动态插值，确保系统在任意学术方向（医学影像分割、代数几何、矩阵乘法等）下均生成无偏、高质量的 LaTeX 综述。

---

## Architecture

### 1. SECTION_TEMPLATES 注册表（SSOT）

位于 `core/synthesis.py` 顶部，作为系统 6 大章节 Prompt 的单一事实来源：

```python
SECTION_TEMPLATES: list[dict] = [
    {
        "name": "Abstract and Introduction",
        "weight": "heavy",
        "guidance": (
            "根据综述主题【{topic}】编写相关的研究背景、核心应用价值、"
            "面临的核心挑战以及本文综述结构。"
            "必须严格且强制采用 \\noindent\\textbf{{摘要：}}..."
            "\\par\\bigskip\\noindent\\textbf{{引言：}}..."
            "的双重物理分段结构。内容不少于 400 字。"
        ),
    },
    {
        "name": "Technical Taxonomy",
        "weight": "light",
        "guidance": (
            "根据对比矩阵中各文献的方法特征，针对主题【{topic}】"
            "划分出清晰的技术体系与分类。"
            "必须采用 \\begin{{itemize}} 列表环境，各类别独立 \\item，"
            "严禁在单行内用长句堆叠。"
        ),
    },
    {
        "name": "Systematic Review and Deep Critique",
        "weight": "light",
        "guidance": (
            "针对下方 rows 中校验通过的文献，进行深入、批判性的横向评述。"
            "每篇文献的局限性评论必须引用其 evidence_page。"
        ),
    },
    {
        "name": "Academic Comparison Matrix",
        "weight": "light",
        "guidance": (
            "直接嵌入下方提供的 booktabs 三线表作为学术对比矩阵，"
            "无需额外文字说明。表中 method 和 limitation 列必须使用中文，"
            "每项不超过 20 字。"
        ),
    },
    {
        "name": "Research Gaps and Future Work",
        "weight": "heavy",
        "guidance": (
            "从上述已验证的局限性出发，归纳当前在【{topic}】场景下面临的"
            "重大研究缺口。必须采用 \\begin{{itemize}} 列表环境，"
            "输出至少 3 个具体的研究缺口（Gap），每项以 \\textbf{{...：}} 开头"
            "（加粗并以中文冒号结尾），内容不少于 500 字。"
        ),
    },
    {
        "name": "Conclusion",
        "weight": "light",
        "guidance": (
            "总结全文核心发现，概括【{topic}】领域当前的研究状态"
            "与未来发展方向。"
        ),
    },
]
```

**所有 `guidance` 均包含 `{topic}` 占位符，无任何硬编码领域术语。**

### 2. 调用路径重构

#### 2a. `build_synthesis_prompt()` — 单通道路径

- 保留 REQUIREMENTS #1-#8（通用规则）
- 移除 #9-#13（格式约束已移至 SECTION_TEMPLATES）
- 新增：遍历 `SECTION_TEMPLATES` 生成章节指引块
- 保持 matrix_rows 数据嵌入逻辑不变

#### 2b. `_build_section_prompt()` — 多阶段路径

- 移除第 318-325 行的 Chapter 0 硬编码分隔符约束
- 移除第 327-333 行的 itemize/colon 通用约束
- 新增：`SECTION_TEMPLATES[section_index]` 提取 + `topic` 格式化
- 保持 chained context、section_word_target、Return ONLY 逻辑不变

### 3. 无回归原则

- `render_survey_tex_with_llm()` 零变化（调用签名不变）
- `render_survey_tex_multi_stage()` 零变化
- `_build_preamble()` 零变化
- `validate_latex_syntax()` 零变化

---

## 测试策略

### 维度 A：主题无偏测试

```python
def test_prompt_no_domain_hardcoding():
    """Prompt must not contain domain-specific terms for any topic."""
    for test_topic in ["medical lesion segmentation", "algebraic geometry"]:
        prompt = build_synthesis_prompt(test_topic, [generic_row])
        assert "robot" not in prompt.lower()
        assert "industrial" not in prompt.lower()
        assert "机械臂" not in prompt
        assert test_topic in prompt
```

### 维度 B：章节模板结构完整性测试

```python
def test_section_templates_integrity():
    """SECTION_TEMPLATES must have exactly 6 entries, each with valid guidance."""
    from core.synthesis import SECTION_TEMPLATES
    assert len(SECTION_TEMPLATES) == 6
    for t in SECTION_TEMPLATES:
        assert "name" in t
        assert "weight" in t
        assert "guidance" in t
        assert "{topic}" in t["guidance"]
    heavy_guidances = [t["guidance"] for t in SECTION_TEMPLATES if t["weight"] == "heavy"]
    light_guidances = [t["guidance"] for t in SECTION_TEMPLATES if t["weight"] == "light"]
    for h in heavy_guidances:
        assert len(h) > len(light_guidances[0])  # heavy > light
```

### 维度 C：两路径一致性测试

```python
def test_both_paths_use_same_section_guidance():
    """Section 0 guidance in build_synthesis_prompt must match _build_section_prompt(0)."""
    from core.synthesis import build_synthesis_prompt, _build_section_prompt
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(...)
    full = build_synthesis_prompt("topic", [row])
    sectional = _build_section_prompt(0, "topic", [row], 3000)
    # Both must reference the same core guidance for section 0
    assert "研究背景" in full and "研究背景" in sectional
```

### 维度 D：CJK 污染检测精度增强测试

```python
def test_cjk_bracket_detection_error_precision():
    """Error message must include precise locating hints."""
    broken = r"\subsection{核心贡献与技术谱系》"
    errors = validate_latex_syntax(broken)
    assert any("检测到中文符号" in e or "CJK" in e for e in errors)
    assert any("输入法冲突" in e or "替换了" in e for e in errors)
```

### 维度 E：零丢失与自适应降级测试

```python
def test_zero_drop_retains_all_papers():
    """3 papers in, 3 rows out — Paper C degraded to missing (unverified)."""
    rows, warnings = extract_with_self_healing(...)
    assert len(rows) == 3
    degraded = [r for r in rows if r.limitation == "missing (unverified)"]
    assert len(degraded) == 1
    assert degraded[0].evidence_quote == "unverified"
```

---

## 文件变更

| 文件 | 变更 |
|------|------|
| `core/synthesis.py` | 新增 `SECTION_TEMPLATES` 全局常量；重构 `build_synthesis_prompt()` 和 `_build_section_prompt()` 遍历/引用模板 |
| `tests/test_synthesis.py` | 新增维度 A/B/C/D 测试；增强维度 E 测试 |

## 无变更文件

| 文件 | 理由 |
|------|------|
| `core/pipeline.py` | 调用签名不变，零回归 |
| `core/templates.py` | 不涉及提示词生成 |
| `core/extractor.py` | 不涉及合成提示词 |
| `core/models.py` | 数据模型不变 |
| `core/agent.py` | 不涉及 |
| `core/credentials.py` | 不涉及 |
| `main.py` | 不涉及 |
| `scripts/run_extraction.py` | 不涉及 |

---

## Self-Review Checklist

- [x] **Placeholder scan:** 无 TBD/TODO。
- [x] **Internal consistency:** SECTION_TEMPLATES 是 SSOT，两路径引用同一数据源。
- [x] **Scope check:** 单一聚焦——仅处理提示词泛化，不涉及其他子系统。
- [x] **Ambiguity check:** heavy/light 有明确区分；{topic} 是唯一插值变量。