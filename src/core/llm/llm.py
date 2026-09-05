import requests
import time
import json
import logging
import os
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


def _http_error_detail(error):
    """提取上游 HTTP 错误的状态码和响应正文，便于定位 400 参数错误。"""
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", "unknown")
    try:
        body = (response.text or "").strip() if response is not None else ""
    except Exception:
        body = ""
    return status_code, body[:2000]


def _local_server_url():
    """读取设置中的本地 llama-server 地址，并规范化 completion 路径。"""
    settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "data", "ui_settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            configured_url = str(json.load(settings_file).get("llm_server_url", "")).strip()
        if configured_url:
            if configured_url.endswith("/completion"):
                return configured_url.rstrip("/")
            return configured_url.rstrip("/") + "/completion"
    except (OSError, ValueError, TypeError):
        pass
    return LLAMA_SERVER_URL


def _fit_local_prompt(prompt, max_tokens):
    """让 prompt 和输出预算适配低上下文 llama-server，避免服务端返回 400。"""
    try:
        context_tokens = max(128, int(os.environ.get("HUMANIZE2_LLM_CONTEXT_TOKENS", "512")))
        output_tokens = max(1, int(max_tokens))
    except (TypeError, ValueError):
        context_tokens, output_tokens = 512, 512

    max_prompt_chars = max(512, (context_tokens - output_tokens - 16) * 4)
    if len(prompt) <= max_prompt_chars:
        return prompt

    truncation_marker = "\n\n[中间上下文已截断以适配本地模型上下文限制]\n\n"
    available_chars = max(0, max_prompt_chars - len(truncation_marker))
    head_chars = available_chars // 3
    tail_chars = available_chars - head_chars
    logger.warning(
        "Truncating local LLM prompt from %d to %d chars (context=%d, output=%d)",
        len(prompt), max_prompt_chars, context_tokens, output_tokens,
    )
    return prompt[:head_chars] + truncation_marker + prompt[-tail_chars:]


def _local_output_budget(max_tokens):
    """限制输出预算，避免低上下文服务端因 n_predict 过大拒绝请求。"""
    try:
        context_tokens = max(128, int(os.environ.get("HUMANIZE2_LLM_CONTEXT_TOKENS", "512")))
        requested_tokens = max(1, int(max_tokens))
    except (TypeError, ValueError):
        context_tokens, requested_tokens = 512, 512
    return min(requested_tokens, max(16, context_tokens // 2))


def _provider_settings():
    """读取当前模型提供商配置；没有 API Key 时始终回退本地模型。"""
    settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "data", "ui_settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        api_key = str(settings.get("openai_api_key", "")).strip()
        if not bool(settings.get("openai_enabled", False)) or not api_key:
            return None
        return {
            "api_key": api_key,
            "base_url": str(settings.get("openai_base_url", "https://api.openai.com/v1")).strip().rstrip("/"),
            "model": str(settings.get("openai_model", "gpt-4o-mini")).strip() or "gpt-4o-mini",
        }
    except (OSError, ValueError, TypeError):
        return None


def _openai_chat(prompt, provider, max_tokens, temperature, top_p, session, timeout):
    request_session = session or create_session()
    own_session = session is None
    try:
        response = request_session.post(
            f"{provider['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
            json={"model": provider["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p},
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            status_code, response_body = _http_error_detail(error)
            logger.error("OpenAI HTTP error %s, response body: %s", status_code, response_body or "<empty>")
            raise RuntimeError(
                f"HTTP error {status_code}: {response_body or 'provider returned an empty error response'}"
            ) from error
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    finally:
        if own_session:
            request_session.close()

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

def chat(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None, timeout=300, max_retries=3):
    provider = _provider_settings()
    logger.info(f"Provider: {provider}")   # 如果 provider 非 None，它会走 OpenAI 分支
    """
    發送HTTP請求到本機llama-server，取得回答
    """
    if stop_event is not None and stop_event.is_set():
        logger.info("LLM request aborted by stop event")
        return "[llm aborted]"

    provider = _provider_settings()
    if provider:
        try:
            return _openai_chat(prompt, provider, max_tokens, temperature, top_p, session, timeout)
        except Exception as error:
            logger.error("OpenAI request failed: %s", error, exc_info=True)
            return f"[llm error] OpenAI request failed: {error}"

    try:
        max_tokens = max(1, int(max_tokens))
        temperature = min(2.0, max(0.0, float(temperature)))
        top_p = min(1.0, max(0.0, float(top_p)))
    except (TypeError, ValueError):
        max_tokens, temperature, top_p = 512, 0.7, 0.9

    max_tokens = _local_output_budget(max_tokens)
    request_session = session or create_session()
    own_session = session is None
    retries = 0
    delay = 5

    local_server_url = _local_server_url()
    prompt = _fit_local_prompt(prompt, max_tokens)
    logger.debug(f"Sending LLM request with prompt length: {len(prompt)}, max_tokens: {max_tokens}, url: {local_server_url}")

    while retries <= max_retries:
        try:
            # ========== 新增：打印完整的请求体 ==========
            payload = {
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "ignore_eos": False
            }
            logger.info(
                "Sending LLM request to %s (prompt_chars=%d, n_predict=%d, temperature=%.2f, top_p=%.2f)",
                local_server_url, len(prompt), max_tokens, temperature, top_p,
            )
            # =========================================

            response = request_session.post(
                local_server_url,
                json=payload,
                timeout=timeout
            )
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
            if retries <= max_retries:
                wait_time = delay * (2 ** (retries - 1))
                logger.warning(f"LLM timeout (attempt {retries}/{max_retries + 1}), retrying in {wait_time}s")
                time.sleep(wait_time)
                continue
            logger.error(f"LLM request timed out after {retries} attempts: {e}")
            return f"[llm error] Request timed out after {timeout * retries} seconds: {e}"

        except requests.exceptions.ConnectionError as e:
            retries += 1
            if retries <= max_retries:
                wait_time = delay * (2 ** (retries - 1))
                logger.warning(f"LLM connection error (attempt {retries}/{max_retries + 1}), retrying in {wait_time}s")
                time.sleep(wait_time)
                continue
            logger.error(f"LLM connection failed after {retries} attempts: {e}")
            return f"[llm error] Connection failed: {e}"

        except requests.exceptions.HTTPError as e:
            # ========== 新增：打印完整的响应体 ==========
            error_response = getattr(e, "response", None)
            status_code = getattr(error_response, "status_code", "unknown")
            try:
                response_body = error_response.text[:2000] if error_response else "No response body"
            except:
                response_body = "Unable to read response body"
            logger.error(f"LLM HTTP error {status_code}, response body: {response_body}")
            # =============================================
            detail = response_body if response_body else "llama-server rejected the request; check its console/log output"
            return f"[llm error] HTTP error {status_code}: {detail}"

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
    流式发送HTTP請求到本機llama-server，逐token返回回答
    """
    if stop_event is not None and stop_event.is_set():
        logger.info("LLM stream request aborted by stop event")
        yield "[llm aborted]"
        return

    provider = _provider_settings()
    if provider:
        try:
            request_session = session or create_session()
            own_session = session is None
            response = request_session.post(
                f"{provider['base_url']}/chat/completion",
                headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
                json={"model": provider["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p, "stream": True},
                timeout=300,
                stream=True,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8", errors="ignore")
                if text.startswith("data:") and text[5:].strip() != "[DONE]":
                    data = json.loads(text[5:].strip())
                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
            if own_session:
                request_session.close()
        except Exception as error:
            logger.error("OpenAI streaming request failed: %s", error)
            yield f"[llm error] OpenAI request failed: {error}"
        return

    request_session = session or create_session()
    own_session = session is None

    try:
        max_tokens = _local_output_budget(max_tokens)
        prompt = _fit_local_prompt(prompt, max_tokens)
        local_server_url = _local_server_url()
        logger.debug(f"Sending streaming LLM request with prompt length: {len(prompt)}")

        # ========== 新增：打印流式请求体 ==========
        stream_payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "ignore_eos": False,
            "stream": True
        }
        logger.info(
            "Sending streaming LLM request to %s (prompt_chars=%d, n_predict=%d, temperature=%.2f, top_p=%.2f)",
            local_server_url, len(prompt), max_tokens, temperature, top_p,
        )
        # =========================================

        response = request_session.post(
            local_server_url,
            json=stream_payload,
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
        # ========== 新增：打印流式错误响应体 ==========
        error_response = getattr(e, "response", None)
        status_code = getattr(error_response, "status_code", "unknown")
        try:
            response_body = error_response.text[:2000] if error_response else "No response body"
        except:
            response_body = "Unable to read response body"
        logger.error(f"LLM stream HTTP error {status_code}, response body: {response_body}")
        # =============================================
        yield f"[llm error] HTTP error {status_code}: {response_body or 'llama-server rejected the request'}"

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