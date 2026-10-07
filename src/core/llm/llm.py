import requests
import time
import json
import logging
import os
import re
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

try:
    from app_paths import get_settings_path
except ImportError:
    from core.app_paths import get_settings_path

try:
    from llm.chat_format import (
        stop_sequences as chat_stop_sequences,
        render_messages as render_chat_messages,
        active_family as active_chat_family,
    )
except ImportError:
    from core.llm.chat_format import (
        stop_sequences as chat_stop_sequences,
        render_messages as render_chat_messages,
        active_family as active_chat_family,
    )


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
    settings_path = get_settings_path()
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
    settings_path = get_settings_path()
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        api_key = str(settings.get("openai_api_key", "")).strip()
        if not bool(settings.get("openai_enabled", False)) or not api_key:
            return None
        base_url = str(settings.get("openai_base_url", "https://api.openai.com/v1")).strip().rstrip("/")
        model = str(settings.get("openai_model", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        provider = {"api_key": api_key, "base_url": base_url, "model": model}
        # 智譜 GLM-4.5/4.6 系列默認開啟深度思考：streaming 時 reasoning 吃光 token 預算、
        # 正文姍姍來遲（頁面長時間「思考中」）。顯式關閉 thinking，讓正文立即流式輸出。
        # 僅對 bigmodel 網關下發該參數，其他 OpenAI 兼容網關不識此字段。
        model_supports_thinking = bool(
            re.match(r"^glm-4\.(5|6)", model)
        )
        if "bigmodel.cn" in base_url and (
            settings.get("openai_thinking_enabled") is False
            or (settings.get("openai_thinking_enabled") is None and model_supports_thinking)
        ):
            provider["disable_thinking"] = True
        return provider
    except (OSError, ValueError, TypeError):
        return None


def _vision_provider():
    """读取视觉模型配置：优先独立 vision_model，缺省沿用对话模型。
    未启用云端 API、或 vision_model 显式为空字符串时返回 None（走本地视觉）。"""
    provider = _provider_settings()
    if not provider:
        return None
    settings_path = get_settings_path()
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        vision_model = str(settings.get("vision_model", "")).strip()
        # 显式空字串 = 關閉雲端視覺（比如當前免費模型不支持圖片）
        if not vision_model:
            return None
        provider = dict(provider)
        provider["model"] = vision_model
    except (OSError, ValueError, TypeError):
        pass
    return provider


def chat_with_image(prompt: str, image_path: str, mime: str = "", max_tokens: int = 800,
                    timeout: int = 120) -> str:
    """用有视觉能力的云端模型分析图片，返回文字描述/回答。

    未配置视觉能力（云端 API 未启用）时返回 None，调用方需自行降级。
    """
    provider = _vision_provider()
    if not provider:
        return None
    try:
        with open(image_path, "rb") as image_file:
            import base64 as _b64
            image_b64 = _b64.b64encode(image_file.read()).decode("ascii")
    except OSError as error:
        return f"[vision error] 读取图片失败: {error}"
    if not mime:
        import mimetypes
        mime = mimetypes.guess_type(image_path)[0] or "image/png"
    request_session = create_session()
    try:
        response = request_session.post(
            f"{provider['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
            json={
                "model": provider["model"],
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ],
                }],
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            status_code, response_body = _http_error_detail(error)
            logger.error("Vision API HTTP error %s, response body: %s", status_code, response_body or "<empty>")
            return f"[vision error] HTTP {status_code}: {response_body or 'provider returned an empty error response'}"
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return _strip_think_blocks(str(content or ""))
    except Exception as error:
        logger.error("Vision API request failed: %s", error, exc_info=True)
        return f"[vision error] {error}"
    finally:
        request_session.close()


# 各模板家族的 prompt 起始標記：帶標記的 prompt 視為已渲染，直接透傳
_TEMPLATE_OPENERS = {"chatml": "<|im_start|>", "gemma": "<start_of_turn>"}

_THINK_OPEN = re.escape(chr(60) + "think" + chr(62))
_THINK_CLOSE = re.escape(chr(60) + "/think" + chr(62))


def _strip_think_blocks(text: str) -> str:
    """移除思考模型  推理塊（非流式決策調用專用；流式由引擎分流到思考區）"""
    if not text:
        return text
    cleaned = re.sub(_THINK_OPEN + r".*?" + _THINK_CLOSE, "", text, flags=re.S)
    return re.sub(_THINK_OPEN + r".*$", "", cleaned, flags=re.S).strip()


def _ensure_templated(prompt: str) -> str:
    """把裸文本 prompt 按當前模型家族包上對話模板。

    背景：Qwen1.5 等低量化模型收到不含模板標記的純指令時會立即吐 EOS
    （回復為空）或續寫式亂碼，GAN/Solve 等決策調用因此全部判空失敗；
    包上 ChatML 後輸出穩定可解析。已渲染（帶家族起始標記）或 legacy
    家族的 prompt 保持原樣，與歷史行為完全一致。
    """
    text = (prompt or "").lstrip()
    opener = _TEMPLATE_OPENERS.get(active_chat_family())
    if opener is None or text.startswith(opener):
        return prompt
    return render_chat_messages([{"role": "user", "content": prompt}])


def _render_local_prompt(prompt: str, system: str = None) -> str:
    """本地 llama-server 使用的 prompt 字符串。

    system 非空時渲染成獨立的 system 輪（ChatML/Gemma/legacy 各自合規），
    讓指令以「系統指令」而非「用戶說的話」送達，避免模型把規則當成
    提示詞注入或用戶內容。
    """
    if system:
        return render_chat_messages(
            [{"role": "user", "content": prompt}],
            system_prompt=system,
        )
    return _ensure_templated(prompt)


_CHATML_SEGMENT_RE = re.compile(r"<\|im_start\|>\s*(system|user|assistant)\s*\n(.*?)<\|im_end\|>", re.S)
_GEMMA_SEGMENT_RE = re.compile(r"<start_of_turn>(user|model)\s*\n(.*?)<end_of_turn>", re.S)


def _to_openai_messages(prompt: str, system: str = None) -> list:
    """構造 OpenAI 風格 messages，系統指令一律走 role=system。

    - prompt 已是 ChatML/Gemma 渲染文本（API 層組裝好的完整對話）時，
      反向解析成結構化 messages——否則 <|im_start|>system 段會被雲端
      模型當成 user 文本，進而懷疑是提示詞注入；
    - system 參數用於決策類調用：指令進 system，用戶原話進 user；
    - 其餘情況單條 user 消息。
    """
    messages = []
    if system and str(system).strip():
        messages.append({"role": "system", "content": str(system).strip()})

    text = (prompt or "").lstrip()
    if text.startswith("<|im_start|>"):
        parsed = _CHATML_SEGMENT_RE.findall(text)
        if parsed:
            for role, content in parsed:
                messages.append({"role": role, "content": content.strip()})
            return messages
    elif text.startswith("<start_of_turn>"):
        parsed = _GEMMA_SEGMENT_RE.findall(text)
        if parsed:
            for role, content in parsed:
                messages.append({"role": "assistant" if role == "model" else "user",
                                 "content": content.strip()})
            return messages

    messages.append({"role": "user", "content": prompt})
    return messages


def _cloud_payload(provider, messages, max_tokens, temperature, top_p, stream=False):
    """構造雲端 chat/completions 請求體；智譜思考模型按需關閉 thinking。"""
    payload = {
        "model": provider["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if stream:
        payload["stream"] = True
    if provider.get("disable_thinking"):
        payload["thinking"] = {"type": "disabled"}
    return payload


def _openai_chat(prompt, provider, max_tokens, temperature, top_p, session, timeout, system=None):
    request_session = session or create_session()
    own_session = session is None
    try:
        response = request_session.post(
            f"{provider['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
            json=_cloud_payload(provider, _to_openai_messages(prompt, system),
                                max_tokens, temperature, top_p),
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
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        # content 可能是 str 或多模態 list（[{"type":"text","text":"..."}]）
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        # 思考模型把最終答案放 content，但 reasoning 字段也可能有內容，一併 strip
        content = _strip_think_blocks(str(content or ""))
        # reasoning 模型常因 max_tokens 不足返回空 content，此時丟出錯誤讓上層走本地 fallback
        if not content:
            reasoning = msg.get("reasoning", "")
            finish = data.get("choices", [{}])[0].get("finish_reason", "")
            raise RuntimeError(
                f"Empty completion from provider (finish_reason={finish!r}, "
                f"reasoning_chars={len(str(reasoning or ''))}, model={provider.get('model')}). "
                f"Thinking model may have exhausted max_tokens before producing content."
            )
        return content
    finally:
        if own_session:
            request_session.close()

RETRY_STRATEGY = Retry(
    # 切換模型後 llama-server 冷啟動可能需要 30~60 秒（期間返回 503），
    # 退避序列約 0/1/2/4/8/16 秒，覆蓋大模型加載窗口。
    total=6,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)

def create_session():
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    # 雲端 API 調用不應經過本機代理（如 ICUBE_PROXY_HOST）
    session.trust_env = False
    return session

def chat(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None, timeout=600, max_retries=3, system: str = None):
    """發送HTTP請求到本機llama-server，取得回答。

    system 非空時以獨立 system 角色發送（雲端 role=system；本地 system 輪），
    避免指令被模型當成用戶文本/提示詞注入。
    """
    provider = _provider_settings()
    logger.info(f"Provider: {provider}")
    # 雲端思考模型（MiniMax-M3/R1）512 token 常被推理吃光導致正文為空；
    # 僅提升「默認預算」的調用，顯式傳值的決策類調用（如 400）保持不變
    if provider and max_tokens == MAX_TOKENS:
        max_tokens = 1024

    if stop_event is not None and stop_event.is_set():
        logger.info("LLM request aborted by stop event")
        return "[llm aborted]"

    if provider:
        try:
            return _openai_chat(prompt, provider, max_tokens, temperature, top_p, session, timeout, system)
        except Exception as error:
            logger.warning("Cloud provider failed, falling back to local llama-server: %s", error)
            # 雲端失敗時繼續走下方本地鏈路，不 return error 字符串

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
    prompt = _render_local_prompt(prompt, system)
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
            stops = chat_stop_sequences()
            if stops:
                payload["stop"] = stops
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

            result = _strip_think_blocks(text)
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


def chat_stream(prompt: str, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, session=None, stop_event=None, system: str = None):
    """
    流式发送HTTP請求到本機llama-server，逐token返回回答
    """
    if stop_event is not None and stop_event.is_set():
        logger.info("LLM stream request aborted by stop event")
        yield "[llm aborted]"
        return

    provider = _provider_settings()
    if provider:
        if max_tokens == MAX_TOKENS:
            max_tokens = 1024  # 雲端思考模型需要推理預算，默認 512 不夠
        cloud_failed = False
        try:
            request_session = session or create_session()
            own_session = session is None
            response = request_session.post(
                f"{provider['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
                json=_cloud_payload(provider, _to_openai_messages(prompt, system),
                                    max_tokens, temperature, top_p, stream=True),
                timeout=300,
                stream=True,
            )
            response.raise_for_status()
            produced_any = False
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8", errors="ignore")
                if text.startswith("data:") and text[5:].strip() != "[DONE]":
                    try:
                        data = json.loads(text[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    # 思考模型在 streaming 裡走 delta.reasoning，直接丟棄（UI 端會分流到思考區）
                    content = delta.get("content", "")
                    if content:
                        produced_any = True
                        yield content
            if own_session:
                request_session.close()
            if produced_any:
                return
            # 思考模型可能因 token 不足整段 stream 都沒 content，視為失敗走本地
            logger.warning("Cloud streaming produced no content (thinking model exhausted tokens?), falling back to local")
        except Exception as error:
            logger.warning("Cloud streaming failed, falling back to local llama-server: %s", error)
        # 雲端失敗：繼續走下方本地鏈路

    request_session = session or create_session()
    own_session = session is None

    try:
        max_tokens = _local_output_budget(max_tokens)
        prompt = _render_local_prompt(prompt, system)
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
        stops = chat_stop_sequences()
        if stops:
            stream_payload["stop"] = stops
        logger.info(
            "Sending streaming LLM request to %s (prompt_chars=%d, n_predict=%d, temperature=%.2f, top_p=%.2f)",
            local_server_url, len(prompt), max_tokens, temperature, top_p,
        )
        # =========================================

        response = request_session.post(
            local_server_url,
            json=stream_payload,
            # 慢機器 prompt 評估可能超過 5 分鐘（換頁嚴重時 ~150ms/token），
            # 與 chat() 的 600s 保持一致，避免主回答流被中途掐斷
            timeout=600,
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