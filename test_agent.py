# 1. 导入我们刚刚在 core 文件夹中写好的 get_llm_agent 函数
from core.agent import get_llm_agent
from langchain_core.prompts import ChatPromptTemplate

def main():
    print("正在连接 API 并初始化 Agent...")
    try:
        # 2. 获取配置好的 llm 实例
        llm = get_llm_agent(temperature=0.2)
        
        # 3. 准备一个简单的学术测试 prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个资深的计算机视觉与机器人安全领域的学术专家。"),
            ("user", "作为文献综述的引言部分，请用一段话简述：为什么机器人在工业场景中的『空间安全监控』是一个亟待解决的问题？")
        ])
        
        # 4. 组装链式调用（LangChain Expression Language - LCEL）
        chain = prompt | llm
        
        print("正在发送请求到大模型...")
        response = chain.invoke({})
        
        # 5. 打印大模型的回答
        print("\n=== [联调成功] 大模型学术回复如下 ===")
        print(response.content)
        print("=====================================\n")
        
    except Exception as e:
        print("\n=== [联调失败] 请根据报错信息进行排查 ===")
        print(e)
        print("=========================================\n")

if __name__ == "__main__":
    main()