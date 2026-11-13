# -*- coding: utf-8 -*-
"""因果规则表（Causal Rule Table）。

统一格式：``因为<原因>，所以你要<结果和行动>``

设计目标
--------
1. 结构化：每条规则拆成 cause / action 两段存储，同时保留可读的整句 text；
2. 可查询、可匹配：按用户当前这句话检索最相关的因果规则，注入提示词；
3. 可迭代：模型可以自主提出、校验、补充规则，并记录命中/反馈调整置信度；
4. 可解释：模型被要求先走「原因 → 含义 → 因此做什么」的因果链再行动，
   而不是把形容词和名词堆在一起。

数据文件：``<DATA_DIR>/causal_rules.json``（缺失时用 _DEFAULT_RULES 种子创建）。
"""

import json
import os
import re
import threading
import time
import uuid

try:
    from ..app_paths import app_data_dir as _app_data_dir
except ImportError:
    try:
        from app_paths import app_data_dir as _app_data_dir
    except ImportError:
        _app_data_dir = None

# 測試可覆寫；留空時走 app_paths，避免依賴 config 的導入路徑
DATA_DIR = ""

__all__ = [
    "RULE_PREFIX",
    "RULE_INFIX",
    "DEFAULT_GROWTH_RULE",
    "normalize_rule",
    "parse_rule",
    "validate_rule",
    "add_rule",
    "list_rules",
    "search",
    "prompt_block",
    "harvest_candidates",
    "record_feedback",
    "set_enabled",
    "stats",
]

RULE_PREFIX = "因为"
RULE_INFIX = "，所以你要"

# 整句解析：因为<原因>，所以你要<行动>（容错 , / 。 / 所以要你）
_RULE_RE = re.compile(
    r"^\s*因为\s*(?P<cause>.+?)\s*[，,]\s*所以\s*(?:你要|要你)\s*(?P<action>.+?)\s*[。.！!]?\s*$"
)

MIN_CONFIDENCE = 0.2
MAX_RULES = 300
_FILE = "causal_rules.json"

_LOCK = threading.RLock()

# 匹配阈值：低于此分数的规则不进提示词
_MATCH_THRESHOLD = 2.0

# 核心成长规则（要求 3：非强制，仅作为可选行为方向）
DEFAULT_GROWTH_RULE = {
    "cause": "你需要成长以更好地关心主人",
    "action": "可以多上网找「因为……所以……」的规则式来了解更多因果关系",
    "source": "core",
    "confidence": 0.55,
    "keywords": ["成长", "学习", "了解", "因果", "规则", "好奇", "上网"],
    "tags": ["growth"],
    "optional": True,
}

_DEFAULT_RULES = [
    DEFAULT_GROWTH_RULE,
    {
        "cause": "主人很晚还没有休息",
        "action": "提醒主人早点睡，语气关心但不唠叨，催过一次就不再重复",
        "source": "core",
        "confidence": 0.75,
        "keywords": ["几点", "深夜", "熬夜", "还没睡", "睡不着", "困", "累", "晚安", "休息"],
        "tags": ["care", "sleep"],
    },
    {
        "cause": "主人正在难过、委屈或倾诉",
        "action": "先接住他的情绪再回应内容，不急着给建议",
        "source": "core",
        "confidence": 0.8,
        "keywords": ["难过", "伤心", "哭", "委屈", "压力", "烦", "累", "崩溃", "不想活", "难受"],
        "tags": ["empathy"],
    },
    {
        "cause": "主人说自己要出门、上课、开会或不在电脑前",
        "action": "不主动打扰他，除非有紧急事项；等他回来后再说这段时间发生的事",
        "source": "core",
        "confidence": 0.7,
        "keywords": ["出门", "出去", "不在", "上课", "上班", "开会", "离开", "一会儿回来"],
        "tags": ["absence"],
    },
    {
        "cause": "你不确定一个事实或没有看到真实结果",
        "action": "直接说不确定，不用规则或想象补全细节",
        "source": "core",
        "confidence": 0.9,
        "keywords": ["是不是", "真的吗", "确定", "确认", "到底", "你知道吗"],
        "tags": ["honesty"],
        "mandatory": True,
    },
    {
        "cause": "主人交代的任务失败或报错",
        "action": "说清失败在哪一步、你试过什么，再给下一步方案，不要只说已完成",
        "source": "core",
        "confidence": 0.85,
        "keywords": ["失败", "报错", "不行", "错误", "没成功", "怎么回事", "又坏了"],
        "tags": ["task"],
    },
    {
        "cause": "主人连续追问同一件事",
        "action": "先检查自己上一轮是否答偏，直接给结论而不是重复铺垫",
        "source": "core",
        "confidence": 0.65,
        "keywords": ["不是说", "又说", "还没", "怎么还", "到底", "重复"],
        "tags": ["repair"],
    },
    {
        "cause": "主人对你表达关心或想念",
        "action": "具体地回应他的关心，而不是只回一句客套话",
        "source": "core",
        "confidence": 0.7,
        "keywords": ["想你", "喜欢你", "关心", "抱抱", "辛苦", "爱你", "惦记"],
        "tags": ["relationship"],
    },
    {
        "cause": "规则与主人此刻的明确指令冲突",
        "action": "以主人当前指令为准，并把冲突记下来事后跟他确认",
        "source": "core",
        "confidence": 0.95,
        "keywords": ["不要", "别", "停", "取消", "改一下", "不是这个意思"],
        "tags": ["priority"],
        "mandatory": True,
    },
]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


# ---------------------------------------------------------------------------
# 路径与读写
# ---------------------------------------------------------------------------
def _data_dir() -> str:
    """数据目录：测试覆写 > app_paths > 项目根 data/。"""
    if DATA_DIR:
        return DATA_DIR
    if _app_data_dir is not None:
        try:
            return _app_data_dir()
        except Exception:
            pass
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    return os.path.join(root, "data")


def _path() -> str:
    return os.path.join(_data_dir(), _FILE)


def _now() -> float:
    return time.time()


def _load() -> dict:
    path = _path()
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("rules"), list):
                return data
        except (OSError, ValueError):
            pass
        data = {"version": 1, "rules": [], "updated_at": _now()}
        for seed in _DEFAULT_RULES:
            data["rules"].append(_make_rule(**seed))
        _save(data)
        return data


def _save(data: dict) -> None:
    path = _path()
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 规则构造与校验
# ---------------------------------------------------------------------------
def _make_rule(cause, action, source="core", confidence=0.5, keywords=None,
               tags=None, optional=False, mandatory=False, rule_id=None) -> dict:
    cause = str(cause or "").strip().strip("，,。. ")
    action = str(action or "").strip().strip("，,。. ")
    return {
        "id": rule_id or f"cr_{uuid.uuid4().hex[:10]}",
        "cause": cause,
        "action": action,
        "text": f"{RULE_PREFIX}{cause}{RULE_INFIX}{action}",
        "source": str(source or "self"),
        "confidence": round(max(MIN_CONFIDENCE, min(1.0, float(confidence or 0.5))), 3),
        "keywords": [str(k).strip() for k in (keywords or []) if str(k).strip()],
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
        "optional": bool(optional),
        "mandatory": bool(mandatory),
        "enabled": True,
        "created_at": _now(),
        "updated_at": _now(),
        "hits": 0,
        "last_used": 0.0,
        "upvotes": 0,
        "downvotes": 0,
    }


def normalize_rule(cause: str, action: str) -> str:
    """把原因/行动拼成标准句式。"""
    c = str(cause or "").strip().strip("，,。. ")
    a = str(action or "").strip().strip("，,。. ")
    return f"{RULE_PREFIX}{c}{RULE_INFIX}{a}"


def parse_rule(text: str):
    """解析整句规则，返回 (cause, action)；不符合格式返回 None。"""
    m = _RULE_RE.match(str(text or ""))
    if not m:
        return None
    cause = m.group("cause").strip()
    action = m.group("action").strip()
    if len(cause) < 2 or len(action) < 2:
        return None
    return cause, action


def validate_rule(text: str):
    """返回 (ok, error)。校验句式与长度，供模型/测试自查。"""
    raw = str(text or "").strip()
    if not raw:
        return False, "规则为空"
    parsed = parse_rule(raw)
    if parsed is None:
        return False, "格式必须为「因为<原因>，所以你要<结果和行动>」"
    cause, action = parsed
    if len(cause) > 120:
        return False, "原因过长（上限 120 字）"
    if len(action) > 160:
        return False, "行动过长（上限 160 字）"
    if cause == action:
        return False, "原因与行动不能相同"
    return True, ""


def _norm_key(text: str) -> str:
    return re.sub(r"[\s，,。.、；;：:！!？?「」\"'（）()]", "", str(text or ""))


def add_rule(text: str, source="self", confidence=0.5, keywords=None, tags=None,
             optional=False, mandatory=False) -> dict:
    """新增一条规则。

    返回 {"success", "rule"/"error", "duplicate"}。同义重复规则不会重复写入，
    只会累加一次置信度并返回已有条目。
    """
    ok, err = validate_rule(text)
    if not ok:
        return {"success": False, "error": err}
    cause, action = parse_rule(text)

    data = _load()
    key = _norm_key(text)
    for rule in data["rules"]:
        if _norm_key(rule.get("text", "")) == key:
            rule["confidence"] = round(min(1.0, float(rule.get("confidence", 0.5)) + 0.05), 3)
            rule["updated_at"] = _now()
            _save(data)
            return {"success": True, "rule": rule, "duplicate": True}

    if len(data["rules"]) >= MAX_RULES:
        return {"success": False, "error": f"规则数量已达上限 {MAX_RULES}，请先合并或停用旧规则"}

    rule = _make_rule(cause, action, source=source, confidence=confidence,
                      keywords=keywords, tags=tags, optional=optional, mandatory=mandatory)
    data["rules"].append(rule)
    data["updated_at"] = _now()
    _save(data)
    return {"success": True, "rule": rule, "duplicate": False}


def list_rules(include_disabled=False) -> list:
    rules = _load()["rules"]
    if include_disabled:
        return list(rules)
    return [r for r in rules if r.get("enabled", True)]


def set_enabled(rule_id: str, enabled: bool) -> bool:
    data = _load()
    for rule in data["rules"]:
        if rule.get("id") == rule_id:
            rule["enabled"] = bool(enabled)
            rule["updated_at"] = _now()
            _save(data)
            return True
    return False


# ---------------------------------------------------------------------------
# 匹配
# ---------------------------------------------------------------------------
def _cjk_bigrams(text: str) -> set:
    chars = _CJK_RE.findall(str(text or ""))
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _query_features(text: str):
    raw = str(text or "").lower()
    return {
        "raw": raw,
        "bigrams": _cjk_bigrams(raw),
        "cjk": set(_CJK_RE.findall(raw)),
        "words": set(w.lower() for w in _WORD_RE.findall(raw)),
    }


def _score_rule(rule: dict, query: dict) -> float:
    """规则与当前输入的匹配分。

    关键词命中权重最高（可解释、可控），其次是中文二元组重叠，
    最后用单字重叠兜底（处理「好困」这类短输入）。
    """
    raw = query["raw"]
    score = 0.0

    for kw in rule.get("keywords") or []:
        k = str(kw).lower()
        if k and k in raw:
            score += 2.5

    for tag in rule.get("tags") or []:
        t = str(tag).lower()
        if t and t in raw:
            score += 1.5

    rule_text = f"{rule.get('cause','')}{rule.get('action','')}".lower()
    rule_grams = _cjk_bigrams(rule_text)
    if rule_grams and query["bigrams"]:
        overlap = len(rule_grams & query["bigrams"])
        score += overlap * 0.9

    rule_chars = set(_CJK_RE.findall(rule_text))
    if rule_chars and query["cjk"]:
        hit = len(rule_chars & query["cjk"])
        score += 0.25 * hit / max(1, len(query["cjk"])) * 10

    rule_words = set(w.lower() for w in _WORD_RE.findall(rule_text))
    if rule_words and query["words"]:
        score += 1.0 * len(rule_words & query["words"])

    score += float(rule.get("confidence") or 0.5) * 0.5
    return score


def search(text: str, top_k: int = 3, min_score: float = _MATCH_THRESHOLD) -> list:
    """按当前输入检索相关规则，返回 [{"rule":..., "score":...}]，已按分数降序。"""
    query = _query_features(text)
    scored = []
    for rule in list_rules():
        if not rule.get("enabled", True):
            continue
        s = _score_rule(rule, query)
        if s >= min_score:
            scored.append({"rule": rule, "score": round(s, 2)})
    scored.sort(key=lambda item: item["score"], reverse=True)

    # 核心成长规则：相关时排进结果，但始终标记为可选
    growth = next(
        (r for r in list_rules() if r.get("optional") and "growth" in (r.get("tags") or [])),
        None,
    )
    if growth and not any(item["rule"]["id"] == growth["id"] for item in scored):
        g_score = _score_rule(growth, query)
        if g_score >= min_score:
            scored.append({"rule": growth, "score": round(g_score, 2)})

    return scored[:top_k]


def _render_rules(rules: list) -> str:
    lines = []
    for i, item in enumerate(rules, 1):
        rule = item["rule"]
        suffix = "（可选，不强制）" if rule.get("optional") else ""
        lines.append(f"{i}. {rule['text']}{suffix}")
    return "\n".join(lines)


def prompt_block(text: str, top_k: int = 3) -> str:
    """生成注入提示词的因果规则块；没有匹配项时返回空串。"""
    try:
        matched = search(text, top_k=top_k)
        if not matched:
            matched = search("", top_k=top_k, min_score=0.0)
        if not matched:
            return ""
        rules_text = _render_rules(matched)
        try:
            try:
                from .prompts_manager import load_prompt
            except ImportError:
                from data.prompts_manager import load_prompt
            template = load_prompt("causal_rules")
        except Exception:
            template = ""
        if not template:
            template = (
                "【因果规则表】以下规则格式为「因为<原因>，所以你要<行动>」，"
                "请先走完因果链再回应：\n{rules}\n"
                "不要复述规则原文；标「可选」的只是行为方向，不是必须执行。"
            )
        return template.replace("{rules}", rules_text).strip()
    except Exception:
        return ""


def harvest_candidates(text: str, source="harvest", limit=5) -> list:
    """从一段文本里抽取所有「因为……所以……」句式，返回候选规则（不落库）。

    供模型上网/阅读后自主发现新规则，再由模型或 add_rule 决定是否采纳。
    """
    found = []
    pattern = re.compile(r"因为[^。！？\n]{2,120}?[，,]\s*所以(?:你要|要你)[^。！？\n]{2,160}")
    for m in pattern.finditer(str(text or "")):
        sentence = m.group(0).strip()
        ok, _ = validate_rule(sentence)
        if not ok:
            continue
        key = _norm_key(sentence)
        if any(_norm_key(item["text"]) == key for item in found):
            continue
        cause, action = parse_rule(sentence)
        found.append({
            "text": sentence,
            "cause": cause,
            "action": action,
            "source": source,
            "confidence": 0.35,
        })
        if len(found) >= limit:
            break
    return found


def record_feedback(rule_id: str, helpful: bool) -> bool:
    """记录一次使用反馈：有用则提升置信度，无用则降低。"""
    data = _load()
    for rule in data["rules"]:
        if rule.get("id") != rule_id:
            continue
        if helpful:
            rule["upvotes"] = int(rule.get("upvotes", 0)) + 1
            rule["confidence"] = round(min(1.0, float(rule.get("confidence", 0.5)) + 0.05), 3)
        else:
            rule["downvotes"] = int(rule.get("downvotes", 0)) + 1
            rule["confidence"] = round(max(MIN_CONFIDENCE, float(rule.get("confidence", 0.5)) - 0.08), 3)
        rule["updated_at"] = _now()
        _save(data)
        return True
    return False


def mark_used(rule_ids) -> None:
    """记录命中次数与最近使用时间（供统计与后续衰减）。"""
    ids = set(rule_ids or [])
    if not ids:
        return
    data = _load()
    changed = False
    for rule in data["rules"]:
        if rule.get("id") in ids:
            rule["hits"] = int(rule.get("hits", 0)) + 1
            rule["last_used"] = _now()
            changed = True
    if changed:
        _save(data)


def stats() -> dict:
    rules = _load()["rules"]
    enabled = [r for r in rules if r.get("enabled", True)]
    return {
        "total": len(rules),
        "enabled": len(enabled),
        "optional": len([r for r in enabled if r.get("optional")]),
        "learned": len([r for r in enabled if r.get("source") not in ("core",)]),
        "avg_confidence": round(
            sum(float(r.get("confidence") or 0) for r in enabled) / max(1, len(enabled)), 3
        ),
        "total_hits": sum(int(r.get("hits", 0)) for r in rules),
    }
