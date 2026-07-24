import requests
import time
import json
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from config import LLAMA_SERVER_URL, LLAMA_SERVER, MAX_TOKENS, TEMPERATURE, TOP_P
except ImportError:
    LLAMA_SERVER = "http://127.0.0.1:8080"
    LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
    MAX_TOKENS = 512
    TEMPERATURE = 0.7
    TOP_P = 0.9

logger = logging.getLogger(__name__)

RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)

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
        logger.info("LLM request aborted by stop event")
        return "[llm aborted]"

    request_session = session or create_session()
    own_session = session is None
    retries = 0
    max_retries = 3
    delay = 5

    logger.debug(f"Sending LLM request with prompt length: {len(prompt)}, max_tokens: {max_tokens}")

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
                timeout=300
            )

            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode LLM response as JSON: {e}")
                try:
                    text = response.text[:500]
                    logger.debug(f"Raw response: {text}")
                    return f"[llm error] Invalid response format: {text[:100]}..."
                except:
                    return "[llm error] Failed to parse response"

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

            result = text.strip()
            logger.debug(f"LLM request successful, response length: {len(result)}")
            return result

        except requests.exceptions.ReadTimeout as e:
            retries += 1
            wait_time = delay * (2 ** (retries - 1))
            logger.warning(f"LLM timeout (attempt {retries}/{max_retries}), retrying in {wait_time}s")
            if retries <= max_retries:
                time.sleep(wait_time)
                continue
            logger.error(f"LLM request timed out after {max_retries} attempts: {e}")
            return f"[llm error] Request timed out after {300 * max_retries} seconds: {e}"

        except requests.exceptions.ConnectionError as e:
            retries += 1
            wait_time = delay * (2 ** (retries - 1))
            logger.warning(f"LLM connection error (attempt {retries}/{max_retries}), retrying in {wait_time}s")
            if retries <= max_retries:
                time.sleep(wait_time)
                continue
            logger.error(f"LLM connection failed after {max_retries} attempts: {e}")
            return f"[llm error] Connection failed: {e}"

        except requests.exceptions.HTTPError as e:
            logger.error(f"LLM HTTP error: {e}")
            status_code = response.status_code if response else "unknown"
            return f"[llm error] HTTP error {status_code}: {e}"

        except Exception as e:
            if stop_event is not None and stop_event.is_set():
                logger.info("LLM request aborted by stop event")
                return "[llm aborted]"
            logger.error(f"LLM unexpected error: {type(e).__name__}: {e}")
            return f"[llm error] {type(e).__name__}: {e}"

        finally:
            if own_session:
                request_session.close()


def chat_stream(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None):
    """
    流式发送HTTP请求到本機llama-server，逐token返回回答
    """
    if stop_event is not None and stop_event.is_set():
        logger.info("LLM stream request aborted by stop event")
        yield "[llm aborted]"
        return

    request_session = session or create_session()
    own_session = session is None

    try:
        logger.debug(f"Sending streaming LLM request with prompt length: {len(prompt)}")

        response = request_session.post(
            LLAMA_SERVER_URL,
            json={
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "ignore_eos": False,
                "stream": True
            },
            timeout=300,
            stream=True
        )

        response.raise_for_status()

        full_text = ""
        received_data = False
        line_count = 0
        
        for line in response.iter_lines(chunk_size=1024):
            if stop_event is not None and stop_event.is_set():
                logger.info("LLM stream request aborted by stop event during iteration")
                break
            
            if not line:
                continue
                
            line_count += 1
            line_str = line.decode('utf-8', errors='ignore').strip()
            
            if line_str.startswith('data:'):
                received_data = True
                data_str = line_str[5:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        if isinstance(data, dict):
                            content = data.get('content', '') or data.get('text', '')
                            if content:
                                full_text += content
                                yield content
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse streaming line {line_count}: {e}")
                        continue
        
        if not received_data:
            logger.warning("LLM stream request completed but no data received")
            yield "[llm error] No streaming data received"
        else:
            logger.debug(f"LLM stream request successful, total response length: {len(full_text)}")
                    
    except requests.exceptions.ReadTimeout as e:
        logger.error(f"LLM stream request timed out: {e}")
        yield f"[llm error] Request timed out: {e}"

    except requests.exceptions.ConnectionError as e:
        logger.error(f"LLM stream connection failed: {e}")
        yield f"[llm error] Connection failed: {e}"

    except requests.exceptions.HTTPError as e:
        logger.error(f"LLM stream HTTP error: {e}")
        yield f"[llm error] HTTP error {response.status_code}: {e}"

    except Exception as e:
        if stop_event is not None and stop_event.is_set():
            logger.info("LLM stream request aborted by stop event")
            yield "[llm aborted]"
        else:
            logger.error(f"LLM stream unexpected error: {type(e).__name__}: {e}")
            yield f"[llm error] {type(e).__name__}: {e}"

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