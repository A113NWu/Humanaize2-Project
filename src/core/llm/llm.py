import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import LLAMA_SERVER_URL, LLAMA_SERVER, MAX_TOKENS, TEMPERATURE, TOP_P

# 配置重试策略
RETRY_STRATEGY = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)

# 创建带有重试功能的Session
def create_session():
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def chat(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None):
    """
    發送HTTP請求到本機llama-server，取得回答
    """
    if stop_event is not None and stop_event.is_set():
        return "[llm aborted]"

    request_session = session or create_session()
    own_session = session is None
    retries = 0
    max_retries = 2
    delay = 5  # 重试延迟时间（秒）

    while retries <= max_retries:
        try:
            response = request_session.post(
                LLAMA_SERVER_URL,
                json={
                    "prompt": prompt,
                    "n_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "ignore_eos": False
                },
                timeout=300  # 增加超时时间到5分钟
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
        except requests.exceptions.ReadTimeout as e:
            retries += 1
            if retries <= max_retries:
                print(f"[WARN] LLM timeout, retrying ({retries}/{max_retries})...")
                time.sleep(delay)
                continue
            return f"[llm error] Request timed out after {300 * max_retries} seconds: {e}"
        except requests.exceptions.ConnectionError as e:
            retries += 1
            if retries <= max_retries:
                print(f"[WARN] LLM connection error, retrying ({retries}/{max_retries})...")
                time.sleep(delay)
                continue
            return f"[llm error] Connection failed: {e}"
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
        response = requests.get(target, timeout=5)
        return 200 <= response.status_code < 500
    except Exception:
        return False


def health_check() -> dict:
    """检查LLM服务器健康状态"""
    target = LLAMA_SERVER
    try:
        response = requests.get(target, timeout=5)
        return {
            "status": "healthy" if 200 <= response.status_code < 500 else "unhealthy",
            "status_code": response.status_code,
            "latency": response.elapsed.total_seconds()
        }
    except requests.exceptions.ConnectionError:
        return {"status": "down", "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"status": "down", "error": "Connection timeout"}
    except Exception as e:
        return {"status": "down", "error": str(e)}