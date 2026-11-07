"""computer-control — 让 Aize 看屏幕并直接操作整台电脑。

底层只用 PIL（截图）和 ctypes/user32（键鼠），不引入 pyautogui，
因此在 PyInstaller 冻结环境里也能工作。

动作：
    status / screenshot / look / move / click / drag / scroll
    type / key / hotkey / run_goal / stop

安全：
    - ui_settings.json 的 desktop_control_enabled 为 false 时拒绝一切输入类动作
    - 每个动作执行前检查停止标志；鼠标移到屏幕左上角 (0,0) 也会触发停止
    - run_goal 有步数上限和总时长上限
"""

import ctypes
from ctypes import wintypes
import json
import os
import sys
import threading
import time
from typing import Any, Dict

_STOP = threading.Event()
_LOCK = threading.Lock()
_RUNNING = {"active": False, "goal": "", "steps": 0, "started_at": 0.0}

# ---------------------------------------------------------------- 设置 / 路径


def _project_root() -> str:
    # skills/computer-control/__init__.py -> 上溯三级
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _settings_path() -> str:
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["get_settings_path"])
            return m.get_settings_path()
        except Exception:
            continue
    return os.path.join(_project_root(), "src", "core", "ui", "data", "ui_settings.json")


def _read_settings() -> Dict[str, Any]:
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _enabled() -> bool:
    """desktop_control_enabled 缺省视为开启；显式 false 才关闭。"""
    return bool(_read_settings().get("desktop_control_enabled", True))


def _data_dir() -> str:
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            path = m.app_data_dir()
            if path:
                return path
        except Exception:
            continue
    path = os.path.join(_project_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def _screenshot_dir() -> str:
    path = os.path.join(_data_dir(), "screenshots")
    os.makedirs(path, exist_ok=True)
    return path


# ------------------------------------------------------- 跨实例状态 / 急停信号
#
# 技能模块可能被多次独立加载（importlib 每次新建模块对象），模块级 _STOP/_RUNNING
# 无法跨实例共享。因此运行状态落到 data/desktop_control_state.json，
# 急停信号落到 data/desktop_control.stop（存在即视为请求停止），
# 任何进程/模块实例（包括 WinIsland 插件经 API）都能读状态、发急停。


def _state_path() -> str:
    return os.path.join(_data_dir(), "desktop_control_state.json")


def _stop_path() -> str:
    return os.path.join(_data_dir(), "desktop_control.stop")


def _write_state(**fields) -> None:
    state = {}
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            prev = json.load(f)
        if isinstance(prev, dict):
            state = prev
    except Exception:
        pass
    state.update(fields)
    state["updated_at"] = time.time()
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass


def _read_state() -> Dict[str, Any]:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            return state
    except Exception:
        pass
    return {}


def _stop_requested() -> bool:
    return _STOP.is_set() or os.path.exists(_stop_path())


def _request_stop() -> None:
    """发出紧急停止：置内存标志 + 落停止文件（跨实例/跨进程生效）。"""
    _STOP.set()
    try:
        with open(_stop_path(), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _clear_stop() -> None:
    """新一轮显式操作开始前，清除遗留的急停信号。"""
    _STOP.clear()
    try:
        os.remove(_stop_path())
    except OSError:
        pass


# ---------------------------------------------------------------- ctypes 键鼠

_user32 = None


def _get_user32():
    global _user32
    if _user32 is not None:
        return _user32
    if sys.platform != "win32":
        return None
    try:
        u = ctypes.windll.user32
        try:
            u.SetProcessDPIAware()
        except Exception:
            pass
        _user32 = u
        return u
    except Exception:
        return None


# 常用键 -> 虚拟键码
VK_MAP = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "space": 0x20, "spacebar": 0x20,
    "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "capslock": 0x14, "printscreen": 0x2C, "pause": 0x13,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
for _ch in "abcdefghijklmnopqrstuvwxyz":
    VK_MAP[_ch] = ord(_ch.upper())
for _ch in "0123456789":
    VK_MAP[_ch] = ord(_ch)


def _vk(name: str) -> int:
    key = str(name).strip().lower()
    if key in VK_MAP:
        return VK_MAP[key]
    if len(key) == 1:
        return ord(key.upper())
    raise ValueError(f"未知按键: {name}")


def _check_stop() -> None:
    if _stop_requested():
        _STOP.set()
        raise RuntimeError("已被停止（stop 信号、急停文件或鼠标移到左上角）")
    u = _get_user32()
    if u is not None:
        pt = wintypes.POINT()
        if u.GetCursorPos(ctypes.byref(pt)) and pt.x <= 1 and pt.y <= 1:
            _request_stop()
            raise RuntimeError("鼠标位于屏幕左上角，已触发紧急停止")


def _screen_size() -> Dict[str, int]:
    u = _get_user32()
    if u is None:
        return {"width": 0, "height": 0}
    return {"width": int(u.GetSystemMetrics(0)), "height": int(u.GetSystemMetrics(1))}


def _move(x: int, y: int, duration: float = 0.0) -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    x, y = int(x), int(y)
    if duration and duration > 0:
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        steps = max(1, int(duration * 60))
        for i in range(1, steps + 1):
            _check_stop()
            u.SetCursorPos(int(pt.x + (x - pt.x) * i / steps),
                           int(pt.y + (y - pt.y) * i / steps))
            time.sleep(duration / steps)
    else:
        u.SetCursorPos(x, y)


MOUSEEVENTF = {
    "left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040),
}


def _click(x=None, y=None, button="left", clicks=1, interval=0.08) -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    if x is not None and y is not None:
        _move(x, y)
    down, up = MOUSEEVENTF.get(str(button).lower(), MOUSEEVENTF["left"])
    for _ in range(max(1, int(clicks))):
        _check_stop()
        u.mouse_event(down, 0, 0, 0, 0)
        u.mouse_event(up, 0, 0, 0, 0)
        time.sleep(interval)


def _drag(x1, y1, x2, y2, duration=0.4, button="left") -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    down, up = MOUSEEVENTF.get(str(button).lower(), MOUSEEVENTF["left"])
    _move(x1, y1)
    time.sleep(0.05)
    u.mouse_event(down, 0, 0, 0, 0)
    try:
        _move(x2, y2, duration)
    finally:
        u.mouse_event(up, 0, 0, 0, 0)


def _scroll(amount: int) -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    _check_stop()
    u.mouse_event(0x0800, 0, 0, int(amount) * 120, 0)


def _press_key(name: str, hold: float = 0.05) -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    vk = _vk(name)
    _check_stop()
    u.keybd_event(vk, 0, 0, 0)
    time.sleep(hold)
    u.keybd_event(vk, 0, 0x0002, 0)


def _hotkey(keys) -> None:
    u = _get_user32()
    if u is None:
        raise RuntimeError("当前平台不支持键鼠控制")
    codes = [_vk(k) for k in keys]
    for vk in codes:
        _check_stop()
        u.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    for vk in reversed(codes):
        u.keybd_event(vk, 0, 0x0002, 0)
        time.sleep(0.02)


def _set_clipboard(text: str) -> bool:
    """把文本放进剪贴板（支持中文/emoji），随后用 Ctrl+V 粘贴输入。"""
    if sys.platform != "win32":
        return False
    try:
        # 必须用 WinDLL 并显式声明 64 位句柄/指针的 restype，否则 HANDLE
        # 会被默认的 c_int 截断，GlobalLock 拿到的地址无效。
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.EmptyClipboard.argtypes = []
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.CloseClipboard.argtypes = []

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        size = (len(text) + 1) * 2
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, ctypes.create_unicode_buffer(text), size)
        kernel32.GlobalUnlock(handle)

        opened = False
        for _ in range(8):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.05)
        if not opened:
            kernel32.GlobalFree(handle)
            return False
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                return False
        finally:
            user32.CloseClipboard()
        return True
    except Exception:
        return False


def _type_text(text: str) -> str:
    """优先剪贴板粘贴（可输入中文）；失败则退化为逐字符 ASCII 输入。"""
    text = str(text)
    if not text:
        return "clipboard"
    if _set_clipboard(text):
        time.sleep(0.05)
        _hotkey(["ctrl", "v"])
        return "clipboard"
    for ch in text:
        if ch == "\n":
            _press_key("enter")
        elif ch == "\t":
            _press_key("tab")
        elif 0x20 <= ord(ch) < 0x7F:
            _press_key(ch)
            time.sleep(0.02)
    return "keyboard"


# ---------------------------------------------------------------- 截图 / 视觉


def _screenshot(name: str = "") -> str:
    try:
        from PIL import ImageGrab
    except Exception as error:
        raise RuntimeError(f"截图组件不可用: {error}")
    path = os.path.join(_screenshot_dir(), (name or time.strftime("screen_%Y%m%d_%H%M%S")) + ".png")
    image = ImageGrab.grab(all_screens=True)
    image.save(path)
    return path


def _look(prompt: str, image_path: str = "", max_tokens: int = 600) -> Dict[str, Any]:
    """截图并让视觉模型回答。视觉模型未配置/不可用时返回可读的降级信息。
    glm-4.6v-flash 是免费模型，限流严格（HTTP 429 / code 1305），自动重试。"""
    path = image_path or _screenshot()
    try:
        from llm import llm as llm_mod
    except ImportError:
        from core.llm import llm as llm_mod
    size = _screen_size()
    result = None
    for attempt in range(6):
        result = llm_mod.chat_with_image(prompt, path, max_tokens=max_tokens, timeout=120)
        if result is None:
            return {
                "success": False,
                "error": "视觉模型未启用：请在设置里填写 vision_model（如 glm-4.6v-flash）",
                "screenshot": path,
                **size,
            }
        if isinstance(result, str) and result.startswith("[vision error]"):
            # 限流（429/1305）退避重试；其他错误直接返回
            if ("429" in result or "1305" in result) and attempt < 5:
                _check_stop()
                time.sleep(6 + attempt * 3)
                continue
            return {"success": False, "error": result, "screenshot": path, **size}
        break
    return {"success": True, "observation": result, "screenshot": path, **size}


# ---------------------------------------------------------------- 目标执行器

_GOAL_PROMPT = """你在直接操作一台 Windows 电脑。当前目标：{goal}

已执行步骤：{steps}

请观察截图（图片尺寸等于屏幕尺寸 {width}x{height}），决定下一步只需一个动作。
只返回 JSON，不要解释：

{{"observation": "你看到的画面要点", "action": "click|double_click|right_click|move|drag|scroll|type|key|hotkey|wait|done",
  "x_ratio": 0.0, "y_ratio": 0.0, "x2_ratio": 0.0, "y2_ratio": 0.0,
  "text": "", "key": "", "keys": [], "scroll": 0,
  "reason": "为什么做这个动作"}}

规则：
- 坐标一律用 0~1 的相对比例（x_ratio 是横向占比，y_ratio 是纵向占比）
- 需要点击某个控件时，先用观察到的画面定位它的中心
- 目标完成时 action 用 done，并在 observation 里说明完成情况
- 如果画面没有变化或不确定，用 wait
"""


def _parse_step(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.lstrip("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _apply_step(step: Dict[str, Any]) -> str:
    width, height = _screen_size()["width"], _screen_size()["height"]
    action = str(step.get("action", "")).strip().lower()

    def px(key):
        return int(float(step.get(key, 0)) * (width if key.startswith("x") else height))

    if action == "done":
        return "done"
    if action == "wait":
        time.sleep(1.0)
        return "wait"
    if action == "move":
        _move(px("x_ratio"), px("y_ratio"), duration=0.2)
    elif action in ("click", "double_click", "right_click"):
        clicks = 2 if action == "double_click" else 1
        button = "right" if action == "right_click" else "left"
        _click(px("x_ratio"), px("y_ratio"), button=button, clicks=clicks)
    elif action == "drag":
        _drag(px("x_ratio"), px("y_ratio"), px("x2_ratio"), px("y2_ratio"))
    elif action == "scroll":
        _scroll(int(step.get("scroll", -3) or -3))
    elif action == "type":
        return f"type({_type_text(step.get('text', ''))})"
    elif action == "key":
        _press_key(step.get("key", ""))
    elif action == "hotkey":
        keys = step.get("keys") or []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+") if k.strip()]
        _hotkey(keys)
    else:
        raise ValueError(f"未知 action: {action}")
    return action


def _run_goal(goal: str, max_steps: int = 30, max_seconds: int = 600) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    if not goal:
        return {"success": False, "error": "缺少 goal"}
    max_steps = max(1, min(int(max_steps), 60))
    max_seconds = max(30, min(int(max_seconds), 1800))
    _clear_stop()
    started = time.time()
    history = []
    _RUNNING.update(active=True, goal=goal, steps=0, started_at=started)
    _write_state(active=True, goal=goal, steps=0, max_steps=max_steps,
                 started_at=started, observation="")
    try:
        for index in range(1, max_steps + 1):
            _check_stop()
            if time.time() - started > max_seconds:
                return {"success": False, "error": "超过总时长上限", "steps": history, "stop_reason": "timeout"}
            shot = _screenshot(f"goal_{int(started)}_{index}")
            size = _screen_size()
            prompt = _GOAL_PROMPT.format(
                goal=goal, steps=json.dumps(history[-6:], ensure_ascii=False),
                width=size["width"], height=size["height"])
            raw = _look_prompt(prompt, shot)
            if not raw["success"]:
                return {"success": False, "error": raw.get("error"), "steps": history, "screenshot": shot}
            step = _parse_step(raw["observation"])
            if not step:
                return {"success": False, "error": "模型未返回可解析的动作 JSON",
                        "raw": (raw.get("observation") or "")[:400], "steps": history, "screenshot": shot}
            note = _apply_step(step)
            history.append({"step": index, "action": step.get("action"),
                            "observation": str(step.get("observation", ""))[:120],
                            "reason": str(step.get("reason", ""))[:120]})
            _RUNNING["steps"] = index
            _write_state(active=True, steps=index,
                         observation=str(step.get("observation", ""))[:120])
            if note == "done":
                return {"success": True, "goal": goal, "steps": history,
                        "observation": step.get("observation", ""), "elapsed": round(time.time() - started, 1)}
            time.sleep(0.5)
        return {"success": False, "error": f"达到步数上限 {max_steps}", "steps": history, "stop_reason": "max_steps"}
    except Exception as error:
        return {"success": False, "error": str(error), "steps": history, "stop_reason": "exception"}
    finally:
        _RUNNING.update(active=False, goal="", steps=0, started_at=0.0)
        _write_state(active=False, steps=0, observation="")


def _look_prompt(prompt: str, image_path: str) -> Dict[str, Any]:
    return _look(prompt, image_path, max_tokens=500)


# ---------------------------------------------------------------- 统一入口


def execute(input_data: Any) -> Dict:
    if not isinstance(input_data, dict):
        return {"success": False, "error": "input 必须是 JSON 对象，例如 {\"action\": \"status\"}"}

    action = str(input_data.get("action", "") or "").strip().lower()
    if not action:
        return {"success": True, "actions": [
            "status", "screenshot", "look", "move", "click", "double_click", "right_click",
            "drag", "scroll", "type", "key", "hotkey", "run_goal", "stop"]}

    if action == "status":
        # 状态文件优先（跨实例/跨进程），缺失时退回本实例内存状态
        state = _read_state()
        running = state if state else dict(_RUNNING)
        # updated_at 超过 120s 未刷新且标记 active，说明写状态的进程已死
        if running.get("active") and time.time() - float(running.get("updated_at", 0) or 0) > 120:
            running = dict(running, active=False, stale=True)
        return {"success": True, **_screen_size(), "enabled": _enabled(),
                "running": running, "stopped": _stop_requested()}

    if action == "stop":
        _request_stop()
        return {"success": True, "stopped": True}

    if not _enabled():
        return {"success": False, "error": "桌面控制已在设置中关闭（desktop_control_enabled=false）"}

    if action == "screenshot":
        path = _screenshot(str(input_data.get("name", "")))
        return {"success": True, "screenshot": path, **_screen_size()}

    if action == "look":
        return _look(str(input_data.get("prompt", "描述屏幕上有什么，以及有哪些可点的按钮。")),
                     str(input_data.get("image_path", ""),))

    if action == "run_goal":
        return _run_goal(input_data.get("goal", ""),
                         input_data.get("max_steps", 30), input_data.get("max_seconds", 600))

    try:
        _clear_stop()
        _check_stop()
        if action == "move":
            _move(input_data.get("x"), input_data.get("y"), float(input_data.get("duration", 0) or 0))
            return {"success": True, "action": action}
        if action in ("click", "double_click", "right_click"):
            _click(input_data.get("x"), input_data.get("y"),
                   button="right" if action == "right_click" else str(input_data.get("button", "left")),
                   clicks=2 if action == "double_click" else int(input_data.get("clicks", 1)))
            return {"success": True, "action": action}
        if action == "drag":
            _drag(input_data.get("x"), input_data.get("y"), input_data.get("x2"), input_data.get("y2"),
                  float(input_data.get("duration", 0.4) or 0.4))
            return {"success": True, "action": action}
        if action == "scroll":
            _scroll(int(input_data.get("amount", -3) or -3))
            return {"success": True, "action": action}
        if action == "type":
            return {"success": True, "action": action, "via": _type_text(input_data.get("text", ""))}
        if action == "key":
            _press_key(input_data.get("key", ""))
            return {"success": True, "action": action}
        if action == "hotkey":
            keys = input_data.get("keys") or []
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split("+") if k.strip()]
            _hotkey(keys)
            return {"success": True, "action": action}
    except Exception as error:
        return {"success": False, "action": action, "error": str(error)}

    return {"success": False, "error": f"未知 action: {action}"}
