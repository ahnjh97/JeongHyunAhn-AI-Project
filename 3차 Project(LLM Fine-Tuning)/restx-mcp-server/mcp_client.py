import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        cwd="/home/ubuntu/llm-api",
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            print("사용 가능한 MCP 도구 목록:")
            for tool in tools.tools:
                description = tool.description or "설명 없음"
                print(f"- {tool.name}: {description}")

            result = await session.call_tool(
                "ask_unity_tutor",
                arguments={
                    "question": "Unity에서 Rigidbody와 CharacterController의 차이를 설명해줘."
                },
            )

            print("\n도구 호출 결과:")
            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)
                else:
                    print(content)


if __name__ == "__main__":
    asyncio.run(main())
