import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 1. 自动读取根目录下的 .env 文件并加载为系统环境变量
load_dotenv()

def get_llm_agent(temperature: float = 0.2) -> ChatOpenAI:
    """
    初始化并返回大语言模型 Agent 实例。
    
    参数:
        temperature: 温度系数，0.0-1.0。
                     学术综述需要严谨（幻觉低），因此默认设置为 0.2 较低值。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o") # 如果没配置，默认用 gpt-4o

    # 安全检查
    if not api_key:
        raise ValueError("未检测到 OPENAI_API_KEY，请检查根目录下的 .env 文件是否配置正确。")

    # 2. 初始化 OpenAI 兼容的聊天模型实例
    llm = ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        max_retries=2,       # 失败时自动重试 2 次
        timeout=60.0         # 请求超时设置，防止网络拥堵卡死
    )
    
    return llm