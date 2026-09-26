"""社交活動技能：Aize 在聊天中被邀請（或主動想）去社交平台逛逛時，觸發完整社交流程。

設計要點：
- 去不去由 Aize 自己決定——技能描述已說明她可以拒絕（拒絕 = 不調用本技能、正常聊天回覆即可）
- 實際流程由閒置引擎 IdleEngine._do_social_activity 完成（收集內容 → Aize 決策 → 執行動作），
  本技能只負責找到正在運行的引擎實例並在後台線程觸發，立即返回以免阻塞聊天
- 引擎實例查找：優先掃 sys.modules 中已加載的 idle 模塊（保證拿到 live 實例），
  兼容 ui.idle / idle / core.ui.idle 等模塊名；最後才按名導入兜底
"""

import threading
from typing import Any, Dict

_IDLE_MODULE_NAMES = ("ui.idle", "idle", "core.ui.idle", "src.core.ui.idle")


def _find_idle_engine():
    """找到運行中的 IdleEngine 實例；找不到返回 None。"""
    import sys
    import importlib
    # 先掃已加載模塊（同一進程內拿到的才是 live 實例）
    for name in _IDLE_MODULE_NAMES:
        mod = sys.modules.get(name)
        if mod is not None:
            inst = getattr(mod, "_idle_engine_instance", None)
            if inst is not None:
                return inst
    # 兜底：按名導入
    for name in _IDLE_MODULE_NAMES:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        inst = getattr(mod, "_idle_engine_instance", None)
        if inst is not None:
            return inst
    return None


def execute(input_data: Any) -> Dict:
    plan = ""
    if isinstance(input_data, dict):
        plan = str(input_data.get("plan") or "").strip()
    elif input_data:
        plan = str(input_data).strip()

    engine = _find_idle_engine()
    if engine is None:
        return {"status": "error", "success": False,
                "output": "空闲引擎当前不可用，暂时去不了社交平台"}
    if getattr(engine, "is_running_gan", False):
        return {"status": "error", "success": False,
                "output": "Aize 正在专心思考别的事情，等她想完再约吧"}

    def _run():
        try:
            engine._do_social_activity(plan=plan or "聊天中提到想去逛逛")
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "success", "success": True,
            "output": "Aize 已经出发去社交平台逛逛了。过程会记录在思考面板；如果她有想分享的见闻或想请教的问题，会主动在聊天里说。"}
