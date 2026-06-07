import requests
from config import LLAMA_SERVER_URL, LLAMA_SERVER, MAX_TOKENS, TEMPERATURE, TOP_P

def chat(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None):
    """
    發送HTTP請求到本機llama-server，取得回答
    """
    if stop_event is not None and stop_event.is_set():
        return "[llm aborted]"

    request_session = session or requests.Session()
    own_session = session is None

    try:
        response = request_session.post(
            LLAMA_SERVER_URL,
            json={
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stop": [
                    "User:",
                    "Assistant:",
                    "</s>"
                ]
            },
            timeout=120
        )

        data = response.json()

        # 支持多种后端返回格式：
        # 1) {"content": "..."}
        # 2) {"text": "..."}
        # 3) {"choices": [{"text": "..."}]}
        # 4) 列表或其他可序列化结构
        text = ""

        if isinstance(data, dict):
            text = data.get("content") or data.get("text") or data.get("result") or ""

            if not text and "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                first = data["choices"][0]
                if isinstance(first, dict):
                    text = first.get("text") or first.get("message", {}).get("content") or ""
                else:
                    text = str(first)

        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                text = first.get("content") or first.get("text") or first.get("result") or ""
            else:
                text = str(first)
        else:
            text = str(data)

        return text.strip()
    except Exception as e:
        if stop_event is not None and stop_event.is_set():
            return "[llm aborted]"
        return f"[llm error] {e}"
    finally:
        if own_session:
            request_session.close()


def is_server_ready(url: str = None) -> bool:
    target = url or LLAMA_SERVER
    try:
        response = requests.get(target, timeout=2)
        return 200 <= response.status_code < 500
    except Exception:
        return False
