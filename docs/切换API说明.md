# SmartSurvey API 与模型切换说明

SmartSurvey 已将 **API Key 的存储与读取迁移到操作系统钥匙串（keyring）**。请在 Streamlit 侧栏的 **Credentials** 区域录入、更新或清除 API Key，不要将真实 Key 写入 Git 或 `.env`。

`.env` 仅作为**开发兼容配置**，用于可选的接口地址与模型名称：

```env
# 可选：服务商接口中转地址（不要在此存放 API Key）
OPENAI_API_BASE="https://api.example.com/v1"

# 可选：模型名称
LLM_MODEL_NAME="gpt-4o"
```

保存 `.env` 后重启应用即可切换 Base URL 与模型；API Key 始终通过 keyring 管理。

---

## 一、录入与更新 API Key

1. 运行 `streamlit run main.py`。
2. 在侧栏 **Update API Key** 输入新 Key（密码框，界面不显示完整 Key）。
3. 点击 **Save API Key**，Key 写入 OS keyring。
4. 需要更换服务商时，重复上述步骤；旧 Key 会被覆盖。

清除 Key：点击 **Clear API Key**。

---

## 二、切换模型与接口地址

只需修改 `.env` 中的 `OPENAI_API_BASE` 与 `LLM_MODEL_NAME`（或对应环境变量），**无需修改 Python 代码**。API Key 仍在 keyring 中，与代码解耦。

### 示例：DeepSeek

```env
OPENAI_API_BASE="https://api.deepseek.com"
LLM_MODEL_NAME="deepseek-chat"
```

在 UI 侧栏保存 DeepSeek 发放的 API Key（勿写入 `.env`）。

### 示例：SiliconFlow

```env
OPENAI_API_BASE="https://api.siliconflow.cn/v1"
LLM_MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
```

### 示例：智谱 AI

```env
OPENAI_API_BASE="https://open.bigmodel.cn/api/paas/v4"
LLM_MODEL_NAME="glm-4"
```

---

## 三、安全提醒

- 不要将真实 API Key 提交到 Git、Docker 镜像或导出文件中。
- 公网部署时，每位用户应使用会话级或用户级凭据存储，不得共用开发者本机 keyring。
- 完整 Key 不会出现在 UI、日志或报错信息中。

---

## 四、本地验证 LLM 连接（可选）

配置 keyring 与 `.env` 后，可运行 `python test_agent.py` 做连通性冒烟测试（需自行保证该脚本与当前 `core.agent` 接口一致）。
