import os
import re
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("unity-game-dev-tutor")

VLLM_SERVER_URL = os.getenv("VLLM_SERVER_URL", "").strip()
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "").strip()
VLLM_MODEL = os.getenv("VLLM_MODEL", "unity-gamedev-llm").strip()


def build_domain_prompt(question: str) -> str:
    return (
        "다음은 Unity, 게임 개발, 게임 수학 질문에 답하는 작업입니다.\n\n"
        "### 지시문:\n"
        "너는 Unity와 게임 개발을 가르치는 한국어 튜터다. "
        "정확한 Unity 공식 용어를 사용한다. "
        "모르면 지어내지 말고 조건을 짧게 설명한다. "
        "답변은 최대 3문장으로 끝낸다. "
        "같은 문장을 반복하지 않는다. "
        "사용자가 코드, C#, 구현, 스크립트를 명시적으로 요청한 경우에만 코드블록을 쓴다.\n\n"
        "사용자 질문에 오타가 있거나 Unity 공식 용어와 맞지 않으면, 가장 가까운 Unity 용어를 짧게 확인한 뒤 답한다. 확실하지 않은 개념은 지어내지 않는다."
        "### 입력:\n"
        f"{question.strip()}\n\n"
        "### 응답:\n"
    )


def wants_code(question: str) -> bool:
    return any(k in question for k in ["코드", "C#", "c#", "구현", "스크립트"])


def postprocess_tutor_answer(text: str, question: str) -> str:
    text = (text or "").strip()

    cut_markers = [
        "### 지시문:",
        "### 입력:",
        "### 응답:",
        "### Instruction:",
        "### Input:",
        "### Response:",
        "추가 입력:",
        "추가 답변:",
        "추가 질문:",
        "\n\n###",
    ]

    for marker in cut_markers:
        if marker in text:
            text = text.split(marker)[0].strip()

    if not wants_code(question):
        for marker in ["```csharp", "``` csharp", "```cs", "```"]:
            if marker in text:
                text = text.split(marker)[0].strip()

    sentences = re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+|(?<=요\.)\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    deduped = []
    seen = set()
    for sentence in sentences:
        key = re.sub(r"\s+", " ", sentence).replace("**", "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)

    if wants_code(question):
        return " ".join(deduped[:5]).strip()

    return " ".join(deduped[:3]).strip()


def mock_inference(question: str) -> str:
    return (
        "[Mock 응답] VLLM_SERVER_URL 환경변수가 설정되지 않아 임시 응답을 반환합니다.\n"
        f"질문: {question}"
    )


def extract_vllm_text(data) -> str:
    if isinstance(data, dict):
        choices = data.get("choices")
        if choices:
            choice = choices[0]

            if isinstance(choice, dict):
                if "text" in choice:
                    return str(choice["text"])

                message = choice.get("message")
                if isinstance(message, dict):
                    return str(message.get("content") or "")

        if "text" in data:
            return str(data["text"])

        if "answer" in data:
            return str(data["answer"])

    return str(data)


def call_vllm_server(question: str) -> str:
    prompt = build_domain_prompt(question)

    headers = {
        "Content-Type": "application/json",
    }

    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    payload = {
        "model": VLLM_MODEL,
        "prompt": prompt,
        "max_tokens": 90,
        "temperature": 0.0,
        "top_p": 1.0,
        "frequency_penalty": 0.3,
        "presence_penalty": 0.0,
        "stop": [
            "### 지시문:",
            "### 입력:",
            "### 응답:",
            "### Instruction:",
            "### Input:",
            "### Response:",
            "추가 입력:",
            "추가 답변:",
            "추가 질문:",
            "\n\n###",
        ],
    }

    if not wants_code(question):
        payload["stop"].extend([
            "```",
            "```csharp",
            "``` csharp",
            "```cs",
        ])

    response = requests.post(
        VLLM_SERVER_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    raw_text = extract_vllm_text(response.json())
    answer = postprocess_tutor_answer(raw_text, question)

    if not answer:
        return "답변을 생성하지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요."

    return answer


@mcp.tool()
def health_check() -> str:
    """Unity/GameDev 튜터 MCP 서버 상태를 확인합니다."""
    if VLLM_SERVER_URL:
        return f"MCP 서버 정상 동작 중입니다. VLLM 연결 대상: {VLLM_SERVER_URL}"
    return "MCP 서버 정상 동작 중입니다. 현재 VLLM_SERVER_URL은 설정되지 않았습니다."


@mcp.tool()
def ask_unity_tutor(question: str) -> str:
    """Unity/GameDev 도메인 튜터에게 질문합니다."""
    question = (question or "").strip()

    if not question:
        return "질문이 비어 있습니다."

    if not VLLM_SERVER_URL:
        return mock_inference(question)

    try:
        return call_vllm_server(question)
    except requests.exceptions.Timeout:
        return "GPU 추론 서버 응답 시간이 초과되었습니다."
    except requests.exceptions.ConnectionError:
        return "GPU 추론 서버에 연결할 수 없습니다."
    except requests.exceptions.HTTPError as exc:
        body = ""
        if exc.response is not None:
            body = exc.response.text[:500]
        return f"GPU 추론 서버 HTTP 오류가 발생했습니다: {exc}\n{body}"
    except Exception as exc:
        return f"GPU 추론 서버 호출 중 오류가 발생했습니다: {exc}"


@mcp.tool()
def explain_unity_concept(concept: str) -> str:
    """Unity 또는 게임 개발 개념을 한국어로 설명합니다."""
    concept = (concept or "").strip()

    if not concept:
        return "설명할 Unity/GameDev 개념이 비어 있습니다."

    question = f"{concept}에 대해 Unity 초보자도 이해하기 쉽게 설명해줘."
    return ask_unity_tutor(question)


if __name__ == "__main__":
    mcp.run()