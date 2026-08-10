## 一、 引言：AI 编码范式下工程师的再定义

在完成 SmartSurvey 项目的开发后，我深刻体会到：当 LLM 能独立承担起编写代码、执行命令的工作时，软件工程师的核心价值变为了把控系统的工程边界、设计降级护栏以及对物理环境碰撞时的排错决策。

LLM 可以极其高效地编写代码、实现计划，但它无法替人类回答“系统的边界在哪里”、“如何保证云端与本地环境的平滑降级”，更无法对“生成结果是否符合预期”承担最终责任。Superpowers 技能框架为我们提供了流程脚手架，但决定系统工程深度与交付质量的，依然是人类工程师对规约、测试及真实物理环境碰撞时的判断力。

---

## 二、 Superpowers 技能效能评估与批判

在整个开发周期中，Superpowers 的七步工作流提供了强大的纪律约束，但不同技能的表现也不尽相同：

1. 发挥最大作用的技能：
   * `brainstorming`：这是最有价值的技能。它通过连续质询，将我最初“做一个万能综述生成器”的模糊想法收敛为一个结构清晰、具备最小可验证闭环、扩展功能强力而富有潜力的项目。
   * `test-driven-development`：强迫 Agent“先红后绿”。如果没有测试的硬性锚定，Agent 在重构长文合成与缓存机制时极易引入破坏性改动。
2. “形式大于实质”的技能：
   * 在处理简单或者小范围的运维修改（如修改 `Dockerfile` 的基础镜像或添加简单的 `.bat` 批处理命令）时，就无需严格遵循完整的 7 步 Skill 流程，这会带来冗长的 Prompt 确认与上下文切换开销。
3. 最有效的 Prompt / Context 策略：
   * 带具体文件路径和错误处理要求的精准 Prompt：模糊的提示词效用不高（比如“请帮我重构代码”或者“检查错误”），需要提供明确的上下文约束。例如：“修改 `core/agent.py`，增加 `gateway_retry` 装饰器，必须捕获 `InternalServerError` 与 `APITimeoutError`，使用 2s/4s/8s 指数退避，并透传 `on_retry` 钩子以触发 Streamlit `st.warning` 提示。”

---

## 三、 TDD 强制与 Subagent 协作分析

### 1. TDD：智能体防脱轨的安全缆绳
在 AI 协作场景下，TDD 绝非阻碍，而是保证 Agent 产出质量的兜底机制。
* **典型案例**：在引入 API 重试机制时，`main.py` 调用了 `create_extraction_fn(on_retry=...)`。由于单模块单元测试是 Mock 化的，导致 `core/agent.py` 函数定义中缺少 `on_retry` 参数的缺陷逃过了常规测试，并在 UI 运行阶段抛出了 `TypeError`。
* **反思与修复**：通过引入 `tests/test_e2e_smoke.py` 端到端烟雾测试，强迫 Agent 在编写实现前先定义全链路调用断言。测试框架直接在 CI 阶段拦截了参数签名脱节问题，证明了“先红后绿”在防止 Agent 写错代码反复调试上的重要性。

### 2. Subagent 自主运行时长与最优 Task 颗粒度
* 自主运行上限：单个 Subagent 在不偏离主题的前提下，能够稳定自主推进约 10–15 分钟。再往上，会因为上下文膨胀导致 LLM 发生“上下文漂移”。
* 最优 Task 颗粒度：“单一职责 + 明确断言”。例如：将“Streamlit 页面缓存优化”与“Windows 启动脚本编写”拆分为两个独立的 Prompt。合并任务会导致 LLM 倾向于优先完成简单的 `.bat` 脚本，而在复杂的 PyVis 缓存与 TDD 编写上敷衍偷懒。

---

## 四、 规约与偏离案例剖析

### 1. 规约不清导致 Agent 偏离案例
* 案例：在初期设计 API 网关重试时，SPEC 中仅模糊写道“系统应具备抗网络抖动能力”。Subagent 据此直接使用了 LangChain 默认的 `max_retries=2`。
* 后果：当部署到真实环境时，API 中转网关抛出了 Envoy 代理的 `upstream connection failure` (500/502) 以及 `APITimeoutError`，系统由于没有捕获特定异常并进行长退避，直接向用户弹出了红屏 StackTrace 报错。
* 修正与演进：我们重新修正了 SPEC 与 PLAN，显式定义了 `gateway_retry` 共享装饰器，明确指定了捕获 `InternalServerError` 与 `APITimeoutError` 的 3 次指数退避策略（2s/4s/8s），并将前端警告解耦透传，才彻底解决了网关抖动问题。

### 2. “冷启动”第二 Agent 试运行的启示
用全新的 Agent 仅凭 `SPEC.md` + `PLAN.md` 试运行时，暴露了大量隐性假设导致与用户系统不匹配的问题（例如默认假设本地存在可用的 LaTeX 编译环境）。这逼迫我们将“云端无头降级”与“双层模板 LaTeX 导言区锁死”等默认设定沉淀回 SPEC 中。

---

## 五、 真实工程硬边界：凭据安全、物理瓶颈与分发闭环

### 1. 凭据威胁模型与三级降级架构
为了应对公网部署与无头容器环境，系统设计了三级凭据存储与降级机制：$\text{OS Keyring} \longrightarrow \text{.env 环境变量} \longrightarrow \text{st.session\_state 内存降级}$
在 Streamlit Cloud / Docker 无头 Linux 容器中，系统自动捕获 `NoKeyringError` 并平滑降级至内存存储，实现了公网 100% 零红屏崩溃。

### 2. 分发与物理瓶颈倒逼的架构进化
在实现多端分发（Windows 本地脚本 / Docker / Streamlit Cloud）的过程中，真实世界的物理瓶颈逼迫我们想清楚了多个隐蔽问题：
1. 云端 60 秒 WebSocket 物理超时：Streamlit Cloud 的免费容器存在 0.5 vCPU 限制与 60s 超时截断，这倒逼我们引入了 `@st.cache_data` 缓存机制、PyVis 懒加载以及 120s 客户端 Timeout，避免了长文合成时出现 TLE 报错。
2. Windows 环境 PATH 污染陷阱：在编写 `run_windows.bat` 本地启动脚本时，遭遇了安装有 Anaconda 的机器上全局 `e:\Anaconda3\python.exe` 抢占环境变量、导致报错 `No module named streamlit` 的问题。我们通过在批处理中显式锁定虚拟环境路径 `".venv\Scripts\python.exe"`，彻底消除了环境污染。

---

## 六、 重做思考与对 Superpowers 的批判

### 1. 对 Superpowers 的批判
* **核心假设**：Superpowers 假设“只要需求规约足够清晰，测试足够严密，Agent 就能在纯软件世界里做出可靠的系统”。
* **批判**：该假设忽略了软件系统与复杂物理现实碰撞时的非确定性。无论是 Anaconda 的环境变量抢占、Envoy 代理网关的 502 抛错，还是 Windows CMD 解释器对 UTF-8 多字节字符的字节截断，这些物理世界的变数与困难都是单纯依靠提示词和规则规约无法提前预知到的。

### 2. 重做思路
如果重新开始这个项目，我会在第一天就建立“端到端烟雾测试”与“网络异常模拟 Mock 环境”，而不是在开发后期遇到 API 网关抖动和参数签名不匹配时才去补救。

### 3. 结语
AI4SE 并不是让 AI 替代工程师，而是将工程师从繁琐的语法拼接中解放出来，去专注于系统的架构护栏、物理边界的应对、严密的规约判断以及真实交付的工程闭环。这正是本次期末项目带给我最重要的工程启示。