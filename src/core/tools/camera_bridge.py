# -*- coding: utf-8 -*-
"""摄像头上传桥。

流程：技能发起取景请求 → 事件汇流排通知网页 → 网页拍照并 POST 回
``/api/camera/frame`` → 技能拿到本地图片路径（再由视觉模型读取）。

同一个进程内用线程事件同步，不落任何额外的网络依赖。
"""
import os
import threading
import uuid

_lock = threading.Lock()
_pending = {}


class _FrameRequest:
    def __init__(self):
        self.event = threading.Event()
        self.path = ""
        self.error = ""


def _publish_camera_event(request_id: str, prompt: str) -> None:
    try:
        from thinking_engine_api import publish_engine_event
    except ImportError:
        from core.thinking_engine_api import publish_engine_event
    publish_engine_event({
        "type": "camera_request",
        "id": request_id,
        "prompt": str(prompt or ""),
    })


def request_frame(prompt: str = "", timeout: float = 20.0) -> dict:
    """发起一次取景请求并等待网页回传。

    返回 ``{"ok": True, "path": ...}`` 或 ``{"ok": False, "error": ...}``。
    """
    request_id = uuid.uuid4().hex
    request = _FrameRequest()
    with _lock:
        _pending[request_id] = request
    try:
        _publish_camera_event(request_id, prompt)
        if not request.event.wait(max(1.0, float(timeout or 20.0))):
            return {
                "ok": False,
                "error": "网页没有在超时内回传摄像头画面（面板未打开，或没有允许摄像头权限）",
            }
        if request.error:
            return {"ok": False, "error": request.error}
        if not request.path or not os.path.isfile(request.path):
            return {"ok": False, "error": "摄像头画面没有保存成功"}
        return {"ok": True, "path": request.path}
    finally:
        with _lock:
            _pending.pop(request_id, None)


def submit_frame(request_id: str, path: str = "", error: str = "") -> bool:
    """网页端回传结果（图片路径或错误说明）。"""
    with _lock:
        request = _pending.get(str(request_id or ""))
    if request is None:
        return False
    request.path = path or ""
    request.error = error or ""
    request.event.set()
    return True
