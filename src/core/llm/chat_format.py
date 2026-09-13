"""按本地模型家族渲染對話模板。

歷史：應用統一用 ``User: ... / Assistant:`` 純文本拼接，這與 TinyLlama 等
舊模型相容；但 Qwen1.5 等 ChatML 模型、Gemma 模型有各自的特殊標記，
用錯模板時（尤其低量化模型）會吐出「ACTION: ...」之類的亂碼。

模型家族依設置中的 model_path 文件名判斷；無法識別時沿用舊式格式，
保證向後相容。
"""

import json
import os

try:
    from app_paths import get_settings_path
except ImportError:
    from core.app_paths import get_settings_path

# ChatML：Qwen、Yi、GLM、InternLM、Hermes 等
_CHATML_KEYS = ("qwen", "yi-", "yi1.", "chatglm", "glm-", "internlm", "hermes", "dolphin")
# Gemma：<start_of_turn>/<end_of_turn>
_GEMMA_KEYS = ("gemma",)


def _model_basename() -> str:
    try:
        with open(get_settings_path(), "r", encoding="utf-8") as f:
            settings = json.load(f)
        path = str(settings.get("model_path") or "").strip()
        if path:
            return os.path.basename(path).lower()
    except (OSError, ValueError):
        pass
    return ""


def active_family() -> str:
    """返回當前本地模型的對話模板家族：chatml / gemma / legacy。"""
    name = _model_basename()
    if any(key in name for key in _GEMMA_KEYS):
        return "gemma"
    if any(key in name for key in _CHATML_KEYS):
        return "chatml"
    return "legacy"


def stop_sequences() -> list:
    """該模板需要顯式告知 llama-server 的停止串。"""
    family = active_family()
    if family == "chatml":
        return ["<|im_end|>", "<|im_start|>"]
    if family == "gemma":
        return ["<end_of_turn>"]
    return []


def render_messages(messages, system_prompt: str = "") -> str:
    """把 OpenAI 風格 messages 渲染成當前模型需要的 prompt 字符串。

    legacy 家族保持歷史的 ``User:/Assistant:`` 格式不變。
    """
    family = active_family()

    system_texts = []
    if system_prompt:
        system_texts.append(str(system_prompt).strip())
    turns = []
    for msg in messages or []:
        role = msg.get("role", "")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system_texts.append(content)
        elif role in ("user", "assistant"):
            turns.append((role, content))

    system_text = "\n\n".join(t for t in system_texts if t)

    if family == "chatml":
        parts = []
        if system_text:
            parts.append(f"<|im_start|>system\n{system_text}<|im_end|>")
        for role, content in turns:
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    if family == "gemma":
        # Gemma 沒有獨立 system 輪，把系統提示併入第一輪 user
        parts = []
        for idx, (role, content) in enumerate(turns):
            tag = "user" if role == "user" else "model"
            if idx == 0 and system_text:
                content = f"{system_text}\n\n{content}"
            parts.append(f"<start_of_turn>{tag}\n{content}<end_of_turn>")
        parts.append("<start_of_turn>model\n")
        return "\n".join(parts)

    # legacy：保持與舊版本完全一致
    parts = []
    if system_text:
        parts.extend([system_text, ""])
    for role, content in turns:
        label = "User" if role == "user" else "Assistant"
        parts.append(f"{label}: {content}")
    parts.append("Assistant:")
    return "\n".join(parts)
