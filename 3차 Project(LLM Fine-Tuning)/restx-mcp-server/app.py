import os
import sys
import asyncio

from flask import Flask
from flask_cors import CORS
from flask_restx import Api, Resource, fields

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

app = Flask(__name__)
CORS(app)

api = Api(
    app,
    version="1.0",
    title="Unity/GameDev LLM Tutor API",
    description="Flask-RESTX API server using MCP tool layer",
)

chat_ns = api.namespace("chat", description="Unity/GameDev tutor chatbot")

chat_request = api.model("ChatRequest", {
    "question": fields.String(required=True, description="사용자 질문"),
})

chat_response = api.model("ChatResponse", {
    "status": fields.String(required=True, description="처리 상태"),
    "answer": fields.String(required=True, description="챗봇 답변"),
    "via": fields.String(required=True, description="처리 경로"),
})


async def call_mcp_unity_tutor(question: str) -> str:
    mcp_env = os.environ.copy()
    mcp_env["VLLM_SERVER_URL"] = os.getenv("VLLM_SERVER_URL", "")
    mcp_env["VLLM_API_KEY"] = os.getenv("VLLM_API_KEY", "")
    mcp_env["VLLM_MODEL"] = os.getenv("VLLM_MODEL", "unity-gamedev-llm")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        cwd="/home/ubuntu/llm-api",
        env=mcp_env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "ask_unity_tutor",
                arguments={"question": question},
            )

            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
                else:
                    texts.append(str(content))

            return "\n".join(texts).strip()


@api.route("/health")
class Health(Resource):
    def get(self):
        return {
            "status": "ok",
            "service": "unity/gamedev-llm-api",
            "mcp": "enabled",
        }


@chat_ns.route("")
class Chat(Resource):
    @chat_ns.expect(chat_request)
    @chat_ns.marshal_with(chat_response)
    def post(self):
        payload = api.payload or {}
        question = (payload.get("question") or "").strip()

        if not question:
            return {
                "status": "error",
                "answer": "질문이 비어 있습니다.",
                "via": "flask-restx",
            }, 400

        try:
            answer = asyncio.run(call_mcp_unity_tutor(question))
            return {
                "status": "success",
                "answer": answer,
                "via": "flask-restx -> mcp-client -> mcp-server -> vllm",
            }
        except Exception as exc:
            return {
                "status": "error",
                "answer": f"MCP 도구 호출 중 오류가 발생했습니다: {exc}",
                "via": "flask-restx -> mcp-client",
            }, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
