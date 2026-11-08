"""Autopilot 一次性授權。

規則（與主人約定）：
- 只有主人明確允許（引擎識別主人原話後寫入）才能進入 Autopilot；
- Aize 只能「向主人申請」（mark_pending），不能自己給自己發許可；
- 一次許可只對一輪 Autopilot 有效，退出（quit / 急停 / 出錯）即失效。
"""

import json
import os
import time

_PENDING_TTL = 1800      # 申請後 30 分鐘內主人的回覆才算數
_ASK_COOLDOWN = 7200     # 同一輪申請最多每 2 小時問一次，避免閒時反覆騷擾

_FILE_NAME = "autopilot_permission.json"


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _data_dir() -> str:
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            path = m.app_data_dir()
            if path:
                os.makedirs(path, exist_ok=True)
                return path
        except Exception:
            continue
    path = os.path.join(_project_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def _path() -> str:
    return os.path.join(_data_dir(), _FILE_NAME)


def _read() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def is_granted() -> bool:
    return bool(_read().get("granted"))


def grant(note: str = "") -> None:
    """主人明確允許：寫入一次性許可，並清掉待回覆的申請。"""
    _write({
        "granted": True,
        "granted_at": time.time(),
        "note": str(note or "")[:200],
        "pending_at": 0,
        "pending_thought": "",
        "last_asked_at": _read().get("last_asked_at", 0),
    })


def revoke() -> None:
    """一輪 Autopilot 結束：許可立即失效（保留申請冷卻時間）。"""
    prev = _read()
    _write({
        "granted": False,
        "granted_at": 0,
        "note": "",
        "pending_at": 0,
        "pending_thought": "",
        "last_asked_at": prev.get("last_asked_at", 0),
    })


def mark_pending(thought: str = "") -> bool:
    """記下「她已向主人申請」。返回是否真的需要去問主人（冷卻期內返回 False）。"""
    now = time.time()
    prev = _read()
    last_asked = float(prev.get("last_asked_at", 0) or 0)
    if last_asked and now - last_asked < _ASK_COOLDOWN:
        return False
    _write(dict(prev, granted=False, pending_at=now, pending_thought=str(thought or "")[:300],
                last_asked_at=now))
    return True


def pending() -> dict:
    """有效的待回覆申請；超過 30 分鐘視為失效。"""
    data = _read()
    if not data.get("pending_at"):
        return {}
    if time.time() - float(data.get("pending_at", 0) or 0) > _PENDING_TTL:
        return {}
    return data


def clear_pending() -> None:
    data = _read()
    if data.get("pending_at"):
        _write(dict(data, pending_at=0, pending_thought=""))


def status() -> dict:
    data = _read()
    return {
        "granted": bool(data.get("granted")),
        "granted_at": float(data.get("granted_at", 0) or 0),
        "pending": bool(pending()),
        "pending_thought": str(data.get("pending_thought", "") or ""),
        "last_asked_at": float(data.get("last_asked_at", 0) or 0),
    }
