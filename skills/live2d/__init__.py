"""
Live2D 技能：Aize 控制她的 Live2D 形象

- speak/motion/expression：推命令給 Live2D 網頁執行（說話帶唇形）
- chat：把外部聊天消息注入互動閉環
- danmu_start/danmu_stop：B 站直播間彈幕接入
- start_obs/vcam_guide：虛擬攝像頭（進會議/直播軟件）
- status：查看運行狀態
"""

import os
import sys
import subprocess
from typing import Any, Dict


def _ensure_src_path():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    for p in (os.path.join(project_root, "src"),
              os.path.join(project_root, "src", "core")):
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)


def _get_hub():
    _ensure_src_path()
    try:
        from tools.live2d_hub import get_live2d_hub
    except ImportError:
        from core.tools.live2d_hub import get_live2d_hub
    return get_live2d_hub()


_VCAM_GUIDE = """虛擬攝像頭設置（讓 Aize 的 Live2D 進入會議/直播軟件）：

方案 A — OBS Studio（推薦）：
1. 安裝 OBS Studio（https://obsproject.com/ 免費）
2. 在 OBS 添加來源 → 瀏覽器(Browser) → URL 填 http://localhost:8082/live2d?camera=1&mocap=1
   （camera 模式只顯示 Aize 上半身，自帶背景圖；mocap=1 開啟動作捕捉——
     攝像頭由後端 Python 打開，瀏覽源不需要攝像頭權限）
   勾選「關閉時關閉來源」、寬高填 1280x720
3. 右鍵來源 → 濾鏡 → 色度鍵(Chroma Key) 可去背（頁面已是透明底時可跳过）
4. 點「啟動虛擬攝像頭」
5. 在會議軟件（Teams/Zoom/騰訊會議）攝像頭裡選「OBS Virtual Camera」
6. 聲音：把 OBS 監聽輸出設為虛擬聲卡（如 VB-CABLE），會議軟件麥克風選同一虛擬聲卡

方案 B — 直播軟件直接用瀏覽源：
B站直播姬/抖音直播伴侶 → 添加瀏覽器源 → 同樣填上面的 URL

會議聊天欄/直播彈幕消息：
- B站直播間：調用 danmu_start 填房間號即可自動接入
- 其他來源：POST http://localhost:8082/api/live2d/command
  {"type": "chat_in", "source": "meeting", "user": "名字", "text": "內容"}
人聲語音：打開 Live2D 頁面（非透明模式）點 🎤 按鈕即可語音對話"""


_OBS_CANDIDATES = [
    r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
]


def execute(input_data: Any) -> Dict:
    if isinstance(input_data, dict):
        action = input_data.get("action", "status")
    else:
        return {"success": False, "error": "input must be an object with 'action'"}

    if action == "status":
        try:
            hub = _get_hub()
            result = {"success": True, "hub": hub.status(),
                      "page": "http://localhost:8082/live2d"}
            try:
                from .danmu import danmu_status
            except ImportError:
                from danmu import danmu_status
            result["danmu"] = danmu_status()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    if action == "speak":
        text = str(input_data.get("text", "")).strip()
        if not text:
            return {"success": False, "error": "text is required"}
        cid = _get_hub().push_command({"type": "speak", "text": text})
        return {"success": True, "id": cid}

    if action == "motion":
        group = str(input_data.get("group", "")).strip() or "TapBody"
        cmd = {"type": "motion", "group": group}
        if "index" in input_data:
            try:
                cmd["index"] = int(input_data["index"])
            except (TypeError, ValueError):
                pass
        cid = _get_hub().push_command(cmd)
        return {"success": True, "id": cid}

    if action == "expression":
        name = str(input_data.get("name", "")).strip()
        if not name:
            return {"success": False, "error": "name is required"}
        cid = _get_hub().push_command({"type": "expression", "name": name})
        return {"success": True, "id": cid}

    if action == "chat":
        text = str(input_data.get("text", "")).strip()
        if not text:
            return {"success": False, "error": "text is required"}
        cid = _get_hub().ingest_chat(
            input_data.get("source", "skill"),
            input_data.get("user", "someone"), text)
        return {"success": True, "id": cid}

    if action == "vcam_guide":
        return {"success": True, "guide": _VCAM_GUIDE}

    if action in ("mocap_start", "mocap_stop", "mocap_status"):
        try:
            _ensure_src_path()
            try:
                from voice.mocap import get_motion_capture
            except ImportError:
                from core.voice.mocap import get_motion_capture
            mc = get_motion_capture()
            if action == "mocap_start":
                return {"success": True, **mc.start()}
            if action == "mocap_stop":
                return {"success": True, **mc.stop()}
            return {"success": True, **mc.status()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    if action == "start_obs":
        for path in _OBS_CANDIDATES:
            if os.path.isfile(path):
                try:
                    subprocess.Popen([path, "--startvirtualcam",
                                      "--minimize-to-tray",
                                      "--disable-shutdown-check"],
                                     cwd=os.path.dirname(path))
                    return {"success": True,
                            "message": "OBS 已啟動並開啟虛擬攝像頭",
                            "path": path}
                except Exception as e:
                    return {"success": False, "error": str(e)}
        return {"success": False,
                "error": "找不到 OBS，請先安裝 OBS Studio 或手動啟動虛擬攝像頭",
                "guide": _VCAM_GUIDE}

    if action == "danmu_start":
        room_id = input_data.get("room_id")
        if not room_id:
            return {"success": False, "error": "room_id is required（B站直播間號）"}
        try:
            try:
                from .danmu import start_danmu
            except ImportError:
                from danmu import start_danmu
            hub = _get_hub()
            start_danmu(room_id,
                        on_danmu=lambda u, t: hub.ingest_chat("bilibili", u, t))
            return {"success": True,
                    "message": f"已接入 B 站直播間 {room_id} 的彈幕"}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"danmu start failed: {e}"}

    if action == "danmu_stop":
        try:
            from .danmu import stop_danmu
        except ImportError:
            from danmu import stop_danmu
        stopped = stop_danmu()
        return {"success": True, "stopped": stopped}

    return {"success": False, "error": f"Unknown action: {action}"}
