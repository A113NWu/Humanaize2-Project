"""
ThinkingEngine API Server - OpenAI兼容接口

为AstrBot等外部服务提供OpenAI兼容的API，让消息经过ThinkingEngine的完整思考流程。
QQ-bot和客户端共用同样的处理函数和逻辑。

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
try:
    from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from queue import Queue, Empty

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


class ResponseCollector:
    """响应收集器 - 收集ThinkingEngine的回调响应
    支持流式和同步两种模式，在最后一个块后等待一段时间没有新消息则认为任务完成"""
    
    def __init__(self, timeout=300, completion_wait=5):
        self._queue = Queue()
        self._timeout = timeout
        self._completion_wait = completion_wait
        self._full_reply = ""
        self._thoughts = []
        self._finished = False
        self._last_chunk_time = 0
    
    def callback(self, response):
        """ThinkingEngine回调函数"""
        if response.get("type") == "chat_response":
            reply = response.get("reply", "")
            self._full_reply += reply
            self._last_chunk_time = time.time()
            self._queue.put({"type": "chunk", "content": reply})
        elif response.get("type") == "internal_thought":
            thought = response.get("thought", "")
            self._thoughts.append(thought)
            logger.info(f"[ThinkingEngine] Internal thought: {thought[:100]}...")
            self._queue.put({"type": "thought", "content": thought})
        elif response.get("type") == "gan_complete":
            pass
        elif response.get("type") == "error":
            self._queue.put({"type": "error", "content": response.get("error", "")})
            self._finished = True
    
    def get_chunk(self):
        """获取下一个响应块
        在最后一个块后等待_completion_wait秒，如果没有新消息则返回完成标记"""
        try:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= self._timeout:
                    return {"type": "timeout"}
                
                # 检查是否已经有一段时间没有新消息了
                if self._last_chunk_time > 0:
                    time_since_last_chunk = time.time() - self._last_chunk_time
                    if time_since_last_chunk >= self._completion_wait:
                        return {"type": "done"}
                
                # 如果从未收到任何块，但已经等待了一段时间，也返回done
                if self._last_chunk_time == 0 and elapsed >= self._completion_wait:
                    return {"type": "done"}
                
                # 尝试获取队列中的消息（非阻塞）
                try:
                    return self._queue.get(timeout=0.5)
                except Empty:
                    continue
        except Exception:
            return {"type": "timeout"}
    
    def is_finished(self):
        """检查是否已完成"""
        return self._finished
    
    def set_finished(self):
        """标记完成"""
        self._finished = True
    
    def get_full_reply(self):
        """获取完整回复"""
        return self._full_reply
    
    def get_thoughts(self):
        """获取思考内容"""
        return self._thoughts


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
        """处理聊天完成请求 - OpenAI兼容格式
        QQ-bot和客户端共用同样的处理函数和逻辑，都通过ThinkingEngine队列处理"""
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

        # 必须有ThinkingEngine实例
        if not thinking_engine:
            self._send_error("ThinkingEngine not available", 503)
            return

        # 通知IdleEngine暂停（如果有），优先处理用户消息
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

        # 创建响应收集器
        collector = ResponseCollector(timeout=300)
        
        # 保存原始on_response回调
        original_on_response = thinking_engine.on_response
        
        # 设置临时回调
        thinking_engine.on_response = collector.callback

        try:
            if stream:
                # 通过ThinkingEngine队列提交流式聊天任务
                thinking_engine.queue_chat_stream_task(
                    full_prompt,
                    memory=memory,
                    user_text=user_text,
                    target_info=None
                )
                self._handle_stream_response(collector, state)
            else:
                # 通过ThinkingEngine队列提交聊天任务
                thinking_engine.queue_chat_task(
                    full_prompt,
                    memory=memory,
                    user_text=user_text,
                    personality=personality
                )
                self._handle_sync_response(collector, user_text, memory, state)
        finally:
            # 恢复原始回调
            thinking_engine.on_response = original_on_response

    def _handle_sync_response(self, collector, user_text, memory, state):
        """处理同步（非流式）响应 - 通过ResponseCollector收集ThinkingEngine的响应"""
        try:
            # 等待响应完成（最多等待collector的timeout）
            full_reply = ""
            while True:
                chunk = collector.get_chunk()
                if chunk["type"] == "chunk":
                    full_reply += chunk["content"]
                elif chunk["type"] == "done":
                    # 任务完成，退出循环
                    break
                elif chunk["type"] == "error":
                    full_reply = f"错误: {chunk['content']}"
                    break
                elif chunk["type"] == "timeout":
                    full_reply = "抱歉，我刚才走神了～能再说一遍吗？😊"
                    break

            # 标记完成
            collector.set_finished()

            # 清理回复
            cleaned_reply = clean_reply(full_reply)

            if not cleaned_reply:
                cleaned_reply = "嗯，我在想呢～"

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
                    "prompt_tokens": 0,
                    "completion_tokens": len(cleaned_reply) // 4,
                    "total_tokens": len(cleaned_reply) // 4
                }
            }

            logger.info(f"[ThinkingEngine API] Sync response: '{cleaned_reply[:50]}...'")
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

    def _handle_stream_response(self, collector, state):
        """处理流式响应 - SSE格式
        通过ResponseCollector收集ThinkingEngine的响应，实现QQ-bot和客户端共用同样的处理逻辑"""
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
            
            # 从ResponseCollector获取流式响应
            while True:
                chunk = collector.get_chunk()
                
                if chunk["type"] == "chunk":
                    content = chunk["content"]
                    full_reply += content

                    # 发送SSE块
                    sse_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(sse_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except BrokenPipeError:
                        logger.info("[ThinkingEngine API] Client disconnected")
                        break
                        
                elif chunk["type"] == "thought":
                    thought_content = chunk["content"]
                    thought_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n[思考] {thought_content}"},
                                "finish_reason": None
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(thought_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except BrokenPipeError:
                        pass
                        
                elif chunk["type"] == "error":
                    # 发送错误消息
                    error_content = f"错误: {chunk['content']}"
                    full_reply += error_content
                    error_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": error_content},
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                    except BrokenPipeError:
                        pass
                    break
                    
                elif chunk["type"] == "done":
                    # 任务完成，退出循环
                    logger.info("[ThinkingEngine API] Task completed naturally")
                    break
                elif chunk["type"] == "timeout":
                    # 发送超时消息
                    timeout_content = "抱歉，我刚才走神了～能再说一遍吗？😊"
                    full_reply += timeout_content
                    timeout_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": timeout_content},
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(timeout_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                    except BrokenPipeError:
                        pass
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
            try:
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass

            # 标记完成
            collector.set_finished()

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
