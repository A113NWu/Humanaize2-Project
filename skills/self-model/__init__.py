# -*- coding: utf-8 -*-
"""self-model 技能：让 Aize 随时修改自己的自我人格、情绪词库与自我目标。

对外接口与其他技能一致：execute(input_data) -> dict。
input_data 支持两种形态：
    {"action": "persona_set", "params": {"text": "..."}}
    {"action": "persona_set", "text": "..."}
"""

import importlib
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PERSONA_MOD = False  # False=尚未尝试；None=加载失败；否则为模块对象


def _src_core_dirs():
    """persona.py 所在目录候选（dev 与打包態）。"""
    dirs = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(os.path.join(meipass, "src", "core"))
        dirs.append(os.path.join(meipass, "core"))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        dirs.append(os.path.join(exe_dir, "src", "core"))
        dirs.append(os.path.join(exe_dir, "core"))
    dirs.append(os.path.join(_ROOT, "src", "core"))
    return dirs


def _persona_mod():
    """惰性载入核心 persona 模块；失败返回 None。"""
    global _PERSONA_MOD
    if _PERSONA_MOD is not False:
        return _PERSONA_MOD
    _PERSONA_MOD = None

    for core_dir in _src_core_dirs():
        if os.path.isdir(core_dir) and core_dir not in sys.path:
            sys.path.insert(0, core_dir)

    # 优先按包导入（persona 内部的相对 .config 可正常解析）
    try:
        src_dir = os.path.dirname(os.path.join(_ROOT, "src", "core"))
        if os.path.isdir(src_dir) and src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        _PERSONA_MOD = importlib.import_module("core.persona")
        return _PERSONA_MOD
    except Exception:
        _PERSONA_MOD = None

    # 回退：按文件路径載入（此时 src/core 已在 sys.path，config 可解析）
    for core_dir in _src_core_dirs():
        init = os.path.join(core_dir, "persona.py")
        if not os.path.exists(init):
            continue
        try:
            spec = importlib.util.spec_from_file_location("humanaize_skill_persona", init)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _PERSONA_MOD = mod
            return mod
        except Exception:
            continue
    return None


def _fail(error):
    return {"success": False, "error": str(error)}


def execute(input_data):
    if not isinstance(input_data, dict):
        return _fail("輸入需為 {'action':..., 'params':{...}}")

    action = str(input_data.get("action", "")).strip().lower()
    params = input_data.get("params") if isinstance(input_data.get("params"), dict) else {}

    def _param(key, default=None):
        if key in params:
            return params.get(key)
        return input_data.get(key, default)

    persona = _persona_mod()
    if persona is None:
        return _fail("persona 模块不可用（找不到 src/core/persona.py）")

    if action == "persona_get":
        return {
            "success": True,
            "persona": persona.load_self_persona(),
        }

    if action == "persona_set":
        text = str(_param("text", "") or "").strip()
        if not text:
            return _fail("缺少 text（新的自我人格全文）")
        saved = persona.save_self_persona(text)
        return {"success": True, "persona": saved}

    if action == "persona_append":
        section = str(_param("section", "") or "").strip()
        if not section:
            return _fail("缺少 section（要追加的人格片段）")
        merged = persona.append_self_persona(section)
        return {"success": True, "persona": merged}

    if action == "goal_add":
        text = str(_param("text", "") or "").strip()
        if not text:
            return _fail("缺少 text（目标内容）")
        goal = persona.add_goal(text, source="skill")
        if not goal:
            return _fail("目标创建失败")
        return {"success": True, "goal": goal}

    if action == "goal_list":
        include_done = bool(_param("include_done", False))
        return {"success": True, "goals": persona.list_goals(include_done=include_done)}

    if action == "goal_close":
        key = _param("id", None)
        if key is None:
            key = _param("goal_id", None)
        if key is None:
            key = _param("text", None)
        if key is None:
            return _fail("缺少 id（目标 id 或目标文本）")
        ok = persona.close_goal(key)
        if not ok:
            return _fail(f"没有找到未完成的目标：{key}")
        return {"success": True, "closed": str(key)}

    if action == "emotion_learn":
        text = str(_param("text", "") or "").strip()
        emotion = str(_param("emotion", "") or "").strip()
        note = str(_param("note", "") or "").strip()
        if not text or not emotion:
            return _fail("缺少 text 或 emotion")
        added = persona.learn_emotion(text, emotion, note=note)
        data = persona.list_emotions()
        return {
            "success": True,
            "added": bool(added),
            "learned_count": len(data.get("learned") or []),
        }

    if action == "emotion_list":
        data = persona.list_emotions()
        return {
            "success": True,
            "categories": data.get("categories") or [],
            "learned": data.get("learned") or [],
        }

    if action == "habit_status":
        return {"success": True, "habit": persona.habit_status()}

    return _fail(f"未知動作: {action}")
