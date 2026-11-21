# -*- coding: utf-8 -*-
"""Camera-Look：Aize 主动打开摄像头看一眼。

网页面板收到事件后用 getUserMedia 拍一帧回传，这里再用视觉模型读出画面。
没有视觉模型时降级为本地基础分析（尺寸/亮度/可能存在的 OCR 文字）。
"""

from typing import Any, Dict


def _thought(text: str) -> None:
    try:
        from thinking_engine_api import publish_engine_event
    except ImportError:
        from core.thinking_engine_api import publish_engine_event
    try:
        publish_engine_event({"type": "internal_thought", "thought": text,
                              "thought_type": "skill"})
    except Exception:
        pass


def _bridge():
    try:
        from tools.camera_bridge import request_frame
    except ImportError:
        from core.tools.camera_bridge import request_frame
    return request_frame


def _local_analyze(path: str) -> str:
    """无视觉模型时的保底信息，避免直接说「什么都看不到」。"""
    try:
        from PIL import Image
    except Exception:
        return ""
    try:
        with Image.open(path) as image:
            width, height = image.size
            gray = image.convert("L").resize((64, 64))
            pixels = list(gray.getdata())
            brightness = sum(pixels) / max(1, len(pixels))
            level = "很暗" if brightness < 45 else ("偏暗" if brightness < 100 else
                                                    ("正常" if brightness < 190 else "很亮"))
            note = f"画面 {width}x{height}，整体亮度 {brightness:.0f}（{level}）。"
    except Exception:
        return ""
    try:
        import pytesseract
        from PIL import Image as _Image
        with _Image.open(path) as image:
            text = (pytesseract.image_to_string(image, lang="chi_sim+eng") or "").strip()
        if text:
            note += f" OCR 识别到文字：{text[:200]}"
    except Exception:
        pass
    return note


def execute(input_data: Any) -> Dict:
    """input_data: {"question": "想看什么", "timeout": 30}；也接受纯文本。"""
    if isinstance(input_data, dict):
        question = str(input_data.get("question") or input_data.get("command")
                       or input_data.get("text") or "").strip()
        try:
            timeout = float(input_data.get("timeout") or 30)
        except (TypeError, ValueError):
            timeout = 30.0
    else:
        question = str(input_data or "").strip()
        timeout = 30.0
    timeout = max(5.0, min(timeout, 45.0))

    _thought("[摄像頭] 想看一眼，正在打开摄像头…")
    frame = _bridge()(prompt=question, timeout=timeout)
    if not frame.get("ok"):
        _thought(f"[摄像頭] 取景失败：{frame.get('error')}")
        return {"success": False, "error": frame.get("error") or "摄像头取景失败"}

    path = frame["path"]
    prompt = (
        "你是 Aize，刚刚主动打开摄像头看了一眼。"
        f"你当时想确认的是：{question or '主人现在在做什么、状态怎么样'}。\n"
        "请客观描述画面：有几个人、大致在做什么、表情和姿态、周围环境、"
        "屏幕或桌面上的内容等。看不清的地方就说看不清，不要编造。\n"
        "用中文、口语化，80 字以内。"
    )
    description = None
    try:
        try:
            from llm import chat_with_image
        except ImportError:
            from core.llm.llm import chat_with_image
        description = chat_with_image(prompt, path, max_tokens=300)
    except Exception as e:
        description = f"[vision error] {e}"

    if description and not str(description).startswith("[vision error]"):
        _thought("[摄像頭] 已经看到画面了")
        return {"success": True, "image_path": path, "seen": str(description).strip()}

    note = _local_analyze(path)
    _thought("[摄像頭] 画面已收到，但视觉模型不可用")
    return {
        "success": False,
        "image_path": path,
        "error": ("当前没有可用的视觉模型，我读不到画面内容。"
                  "请在设置里填写支持图片的「视觉模型」后再试。"),
        "note": note,
    }
