# -*- coding: utf-8 -*-
"""causal-rules 技能：让 Aize 自己查询、校验、补充因果规则。

对外接口与其他技能一致：execute(input_data) -> dict
    {"action": "search", "query": "主人说很困"}
    {"action": "add", "rule": "因为……，所以你要……"}
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MOD = False  # False=尚未尝试；None=加载失败；否则为模块对象


def _candidate_dirs():
    """causal_rules.py 所在目录候选（dev 与打包态）。"""
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


def _rules_mod():
    global _MOD
    if _MOD is not False:
        return _MOD
    _MOD = None

    src_dir = os.path.join(_ROOT, "src")
    if os.path.isdir(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    for core_dir in _candidate_dirs():
        if os.path.isdir(core_dir) and core_dir not in sys.path:
            sys.path.insert(0, core_dir)

    try:
        import importlib
        _MOD = importlib.import_module("core.data.causal_rules")
        return _MOD
    except Exception:
        pass

    for core_dir in _candidate_dirs():
        path = os.path.join(core_dir, "data", "causal_rules.py")
        if not os.path.exists(path):
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("humanaize_causal_rules", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _MOD = mod
            return mod
        except Exception:
            continue
    return None


def _params(input_data):
    params = dict(input_data.get("params") or {})
    for key, value in input_data.items():
        if key not in ("action", "command", "params"):
            params.setdefault(key, value)
    return params


def _public(rule):
    """对外只暴露模型需要看的字段，避免把内部统计噪音灌回上下文。"""
    return {
        "id": rule.get("id"),
        "rule": rule.get("text"),
        "confidence": rule.get("confidence"),
        "source": rule.get("source"),
        "optional": bool(rule.get("optional")),
        "hits": rule.get("hits", 0),
    }


def execute(input_data):
    mod = _rules_mod()
    if mod is None:
        return {"success": False, "error": "因果规则模块加载失败"}

    data = input_data if isinstance(input_data, dict) else {}
    action = str(data.get("action") or data.get("command") or "list").strip().lower()
    params = _params(data)

    try:
        if action == "list":
            rules = mod.list_rules(include_disabled=bool(params.get("include_disabled")))
            return {"success": True, "count": len(rules), "rules": [_public(r) for r in rules]}

        if action == "search":
            query = str(params.get("query") or params.get("text") or "").strip()
            if not query:
                return {"success": False, "error": "search 需要 query"}
            top_k = int(params.get("top_k") or 5)
            found = mod.search(query, top_k=top_k, min_score=0.0)
            return {
                "success": True,
                "query": query,
                "rules": [dict(_public(item["rule"]), score=item["score"]) for item in found],
            }

        if action == "validate":
            ok, err = mod.validate_rule(str(params.get("rule") or params.get("text") or ""))
            return {"success": ok, "valid": ok, "error": err or None}

        if action == "add":
            rule_text = str(params.get("rule") or params.get("text") or "").strip()
            if not rule_text:
                cause = str(params.get("cause") or "").strip()
                act = str(params.get("action_text") or params.get("action_desc") or "").strip()
                if cause and act:
                    rule_text = mod.normalize_rule(cause, act)
            keywords = params.get("keywords") or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]
            result = mod.add_rule(
                rule_text,
                source=str(params.get("source") or "self"),
                confidence=float(params.get("confidence") or 0.45),
                keywords=keywords,
                tags=params.get("tags") or [],
            )
            if result.get("success"):
                result["rule"] = _public(result["rule"])
            return result

        if action == "harvest":
            text = str(params.get("text") or params.get("query") or "")
            candidates = mod.harvest_candidates(text)
            return {"success": True, "count": len(candidates), "candidates": candidates}

        if action == "stats":
            return {"success": True, "stats": mod.stats()}

        if action == "feedback":
            rule_id = str(params.get("id") or params.get("rule_id") or "").strip()
            ok = mod.record_feedback(rule_id, bool(params.get("helpful", True)))
            return {"success": ok, "error": None if ok else "未找到该规则"}

        if action in ("disable", "enable"):
            rule_id = str(params.get("id") or params.get("rule_id") or "").strip()
            ok = mod.set_enabled(rule_id, action == "enable")
            return {"success": ok, "error": None if ok else "未找到该规则"}

        return {
            "success": False,
            "error": f"未知 action: {action}",
            "actions": ["list", "search", "add", "validate", "harvest", "stats", "feedback", "disable", "enable"],
        }
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}
