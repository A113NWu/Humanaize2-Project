"""
ThinkingEngine API Server - OpenAI兼容接口

为AstrBot等外部服务提供OpenAI兼容的API，让消息经过ThinkingEngine的完整思考流程。

启动方式：
    python thinking_engine_api.py --port 8082

AstrBot配置：
    provider_source.api_base = "http://127.0.0.1:8082/v1"
"""

import json
import time
import uuid
import threading
import os
import sys
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# 添加路径
core_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, core_dir)
src_dir = os.path.dirname(core_dir)
sys.path.insert(0, src_dir)
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)

try:
    from tools.logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

# 延迟导入llm模块，避免循环依赖
_generate_with_emotion_feedback = None
_generate_with_emotion_feedback_stream = None

def _get_llm_functions():
    """延迟获取LLM函数"""
    global _generate_with_emotion_feedback, _generate_with_emotion_feedback_stream
    if _generate_with_emotion_feedback is None:
        try:
            from llm.llm_enhanced import generate_with_emotion_feedback, generate_with_emotion_feedback_stream
            _generate_with_emotion_feedback = generate_with_emotion_feedback
            _generate_with_emotion_feedback_stream = generate_with_emotion_feedback_stream
        except ImportError as e:
            logger.error(f"Failed to import llm_enhanced: {e}")
            _generate_with_emotion_feedback = _fallback_generate
            _generate_with_emotion_feedback_stream = _fallback_generate_stream
    return _generate_with_emotion_feedback, _generate_with_emotion_feedback_stream


def _fallback_generate(prompt, emotion_monitor=None):
    """回退方案：直接调用llama-server"""
    import requests
    try:
        response = requests.post(
            "http://127.0.0.1:8080/completion",
            json={"prompt": prompt, "n_predict": 512, "temperature": 0.7, "top_p": 0.9, "ignore_eos": False},
            timeout=300
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("content", "") if isinstance(data, dict) else str(data)
        return text.strip(), None
    except Exception as e:
        logger.error(f"Fallback generate error: {e}")
        return f"[error] {e}", None


def _fallback_generate_stream(prompt, emotion_monitor=None):
    """回退方案：直接流式调用llama-server"""
    import requests
    try:
        response = requests.post(
            "http://127.0.0.1:8080/completion",
            json={"prompt": prompt, "n_predict": 512, "temperature": 0.7, "top_p": 0.9, "ignore_eos": False, "stream": True},
            timeout=300,
            stream=True
        )
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1024):
            if not line:
                continue
            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str.startswith('data:'):
                data_str = line_str[5:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        token = data.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.error(f"Fallback stream error: {e}")
        yield f"[error] {e}"


class ThinkingEngineState:
    """共享状态 - 与GUI的ThinkingEngine交互"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._thinking_engine = None
                cls._instance._memory = None
                cls._instance._personality = None
                cls._instance._qq_ui_callback = None
        return cls._instance

    def set_thinking_engine(self, engine):
        self._thinking_engine = engine

    def get_thinking_engine(self):
        return self._thinking_engine

    def set_memory(self, memory):
        self._memory = memory

    def get_memory(self):
        return self._memory

    def set_personality(self, personality):
        self._personality = personality

    def get_personality(self):
        return self._personality

    def set_qq_ui_callback(self, callback):
        self._qq_ui_callback = callback

    def get_qq_ui_callback(self):
        return self._qq_ui_callback


from utils.reply_cleaner import clean_reply


def build_prompt_from_messages(messages, personality_prompt=""):
    """从OpenAI格式的messages构建prompt"""
    parts = []

    # 添加角色提示
    if personality_prompt:
        parts.append(personality_prompt)
        parts.append("")

    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role == 'system':
            parts.append(content)
            parts.append("")
        elif role == 'user':
            parts.append(f"User: {content}")
        elif role == 'assistant':
            parts.append(f"Assistant: {content}")

    parts.append("Assistant:")
    return "\n".join(parts)


def build_context_from_memory(memory, max_messages=8):
    """从memory构建上下文"""
    if not memory:
        return ""

    messages = memory.get("messages", [])[-max_messages:]
    context = "Recent conversation:"
    for msg in messages:
        role = msg.get("role", "").capitalize()
        source = msg.get("source", "")
        content = msg.get("content", "")[:100]

        if source == "user":
            context += f"\n[用户] {content}"
        elif source == "ai_autonomous":
            context += f"\n[Aize主动] {content}"
        elif source == "ai_response":
            context += f"\n[Aize回复] {content}"
        else:
            context += f"\n{role}: {content}"
    return context


class ThinkingEngineAPIHandler(BaseHTTPRequestHandler):
    """OpenAI兼容的API处理器"""

    def log_message(self, format, *args):
        logger.info(f"[ThinkingEngine API] {args[0]}")

    def _send_json(self, data, status=200):
        """发送JSON响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        """发送错误响应"""
        self._send_json({"error": {"message": message, "type": "invalid_request_error"}}, status)

    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)

        if parsed.path == '/v1/models':
            self._handle_list_models()
        elif parsed.path == '/health' or parsed.path == '/':
            self._send_json({"status": "ok", "service": "thinking-engine-api"})
        else:
            self._send_error("Not found", 404)

    def do_POST(self):
        """处理POST请求"""
        parsed = urlparse(self.path)

        if parsed.path == '/v1/chat/completions':
            self._handle_chat_completions()
        else:
            self._send_error("Not found", 404)

    def _handle_list_models(self):
        """返回可用模型列表"""
        models = [
            {
                "id": "thinking-engine",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "humanaize"
            },
            {
                "id": "aize-v2",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "humanaize"
            }
        ]
        self._send_json({"object": "list", "data": models})

    def _handle_chat_completions(self):
        """处理聊天完成请求 - OpenAI兼容格式"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_data = self.rfile.read(content_length)
            body = json.loads(body_data.decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return

        messages = body.get('messages', [])
        stream = body.get('stream', False)
        max_tokens = body.get('max_tokens', 512)
        temperature = body.get('temperature', 0.7)

        if not messages:
            self._send_error("messages is required")
            return

        # 获取共享状态
        state = ThinkingEngineState()
        thinking_engine = state.get_thinking_engine()
        memory = state.get_memory()
        personality = state.get_personality()

        # 通知IdleEngine暂停（如果有），优先处理用户消息
        thinking_engine = state.get_thinking_engine()
        if thinking_engine:
            try:
                thinking_engine.pause_idle()
            except Exception:
                pass

        # 构建角色提示
        personality_prompt = ""
        if personality:
            personality_prompt = getattr(personality, 'description', '') or str(personality)

        # 从messages中提取用户输入
        user_text = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_text = msg.get('content', '')
                break

        # 构建完整prompt（包含上下文）
        context = build_context_from_memory(memory) if memory else ""
        prompt_parts = []
        if personality_prompt:
            prompt_parts.append(personality_prompt)
        if context:
            prompt_parts.append(context)
        prompt_parts.append(build_prompt_from_messages(messages, ""))
        full_prompt = "\n\n".join(prompt_parts)

        logger.info(f"[ThinkingEngine API] Request: user_text='{user_text[:50]}...', stream={stream}")

        if stream:
            self._handle_stream_response(full_prompt, max_tokens, temperature, state)
        else:
            self._handle_sync_response(full_prompt, max_tokens, temperature, user_text, memory, state)

    def _handle_sync_response(self, prompt, max_tokens, temperature, user_text, memory, state):
        """处理同步（非流式）响应"""
        try:
            # 调用ThinkingEngine的LLM生成
            gen_fn, _ = _get_llm_functions()
            reply, _ = gen_fn(prompt)

            # 清理回复
            cleaned_reply = clean_reply(reply)

            if not cleaned_reply:
                cleaned_reply = "嗯，我在想呢～"

            # 保存到memory（如果可用）
            if memory and user_text:
                try:
                    from memory import add, save_memory
                    add(memory, "user", user_text, source="user")
                    add(memory, "assistant", cleaned_reply, source="ai_response")
                    save_memory(memory)
                except Exception as e:
                    logger.error(f"[ThinkingEngine API] Failed to save memory: {e}")

            # 通知QQ UI更新（显示Aize发送的消息）
            qq_callback = state.get_qq_ui_callback()
            if qq_callback:
                try:
                    qq_callback({
                        'type': 'sent',
                        'from': 'Aize',
                        'target_id': 'QQ',
                        'message_type': 'private',
                        'message': cleaned_reply,
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.error(f"[ThinkingEngine API] QQ UI callback error: {e}")

            # 构建OpenAI格式响应
            response = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": cleaned_reply
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt) // 4,
                    "completion_tokens": len(cleaned_reply) // 4,
                    "total_tokens": (len(prompt) + len(cleaned_reply)) // 4
                }
            }

            logger.info(f"[ThinkingEngine API] Response: '{cleaned_reply[:50]}...'")
            self._send_json(response)

        except Exception as e:
            logger.error(f"[ThinkingEngine API] Sync error: {e}")
            self._send_json({
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"抱歉，我刚才走神了～能再说一遍吗？😊"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            })

    def _handle_stream_response(self, prompt, max_tokens, temperature, state):
        """处理流式响应 - SSE格式"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        try:
            # 累积完整回复用于清理和UI更新
            full_reply = ""
            _, stream_fn = _get_llm_functions()
            for token in stream_fn(prompt):
                if not token:
                    continue
                full_reply += token

                chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": "thinking-engine",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": token},
                            "finish_reason": None
                        }
                    ]
                }
                try:
                    self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                    self.wfile.flush()
                except BrokenPipeError:
                    break

            # 发送结束标记
            final_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

            # 通知QQ UI更新（显示Aize发送的消息）
            cleaned_reply = clean_reply(full_reply) if full_reply else ""
            if cleaned_reply:
                qq_callback = state.get_qq_ui_callback()
                if qq_callback:
                    try:
                        qq_callback({
                            'type': 'sent',
                            'from': 'Aize',
                            'target_id': 'QQ',
                            'message_type': 'private',
                            'message': cleaned_reply,
                            'timestamp': time.time()
                        })
                    except Exception as e:
                        logger.error(f"[ThinkingEngine API] QQ UI callback error: {e}")

            logger.info(f"[ThinkingEngine API] Stream response completed: '{full_reply[:50]}...'")

        except Exception as e:
            logger.error(f"[ThinkingEngine API] Stream error: {e}")
            error_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "抱歉，我刚才走神了～能再说一遍吗？😊"},
                        "finish_reason": "stop"
                    }
                ]
            }
            try:
                self.wfile.write(f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass


class ThinkingEngineAPIServer:
    """ThinkingEngine API服务器"""

    def __init__(self, host='127.0.0.1', port=8082):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """启动API服务器（在后台线程中）"""
        if self.running:
            return

        self.server = HTTPServer((self.host, self.port), ThinkingEngineAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="ThinkingEngineAPI")
        self.thread.start()
        self.running = True
        logger.info(f"ThinkingEngine API server started on http://{self.host}:{self.port}")

    def stop(self):
        """停止API服务器"""
        if not self.running:
            return
        self.server.shutdown()
        self.server.server_close()
        self.running = False
        logger.info("ThinkingEngine API server stopped")

    def is_running(self):
        return self.running


# 全局实例
_api_server = None


def get_api_server():
    """获取API服务器全局实例"""
    global _api_server
    if _api_server is None:
        _api_server = ThinkingEngineAPIServer()
    return _api_server


def start_api_server(host='127.0.0.1', port=8082):
    """启动API服务器"""
    server = get_api_server()
    if not server.is_running():
        server.host = host
        server.port = port
        server.start()
    return server


def stop_api_server():
    """停止API服务器"""
    server = get_api_server()
    if server.is_running():
        server.stop()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='ThinkingEngine API Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind')
    parser.add_argument('--port', type=int, default=8082, help='Port to bind')
    args = parser.parse_args()

    print(f"Starting ThinkingEngine API server on http://{args.host}:{args.port}")
    print(f"OpenAI-compatible endpoint: http://{args.host}:{args.port}/v1/chat/completions")
    print(f"Models list: http://{args.host}:{args.port}/v1/models")
    print(f"Health check: http://{args.host}:{args.port}/health")

    server = ThinkingEngineAPIServer(args.host, args.port)
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
