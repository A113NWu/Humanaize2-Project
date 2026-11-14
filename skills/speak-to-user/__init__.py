"""Speak-To-User：Aize 在闲置时主动找主人说话。"""

from typing import Any, Dict


def _publish(message: str) -> None:
    try:
        from thinking_engine_api import publish_engine_event
    except ImportError:
        from core.thinking_engine_api import publish_engine_event
    publish_engine_event({"type": "autonomous_message", "message": message})


def _remember(message: str) -> None:
    try:
        try:
            from memory import load_memory, add, save_memory
        except ImportError:
            from core.memory import load_memory, add, save_memory
        mem = load_memory()
        add(mem, "assistant", message, source="autonomous")
        save_memory(mem)
    except Exception:
        pass


def execute(input_data: Any) -> Dict:
    """input_data: {"message": "..."}；也接受纯文本。"""
    if isinstance(input_data, dict):
        message = input_data.get("message") or input_data.get("text") or ""
    else:
        message = input_data or ""
    message = str(message).strip()
    if not message:
        return {"success": False, "error": "message 不能為空"}

    _publish(message)
    _remember(message)
    return {"success": True, "message": message}
