# -*- coding: utf-8 -*-
"""網頁事件匯流排 + 技能管理 API 的冒煙測試（不需 LLM / 網路）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src", "core") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src", "core"))

from thinking_engine_api import (
    publish_engine_event,
    classify_idle_thought_type,
    _get_skills_manager,
    _resolve_skills_dir,
    _SKILL_EXECUTE_WHITELIST,
    _idle_event_bus,
)


def test_classify_idle_thought_type():
    assert classify_idle_thought_type("[Social] Aize 選擇去逛逛") == "social"
    assert classify_idle_thought_type("[Thinking Direction] AI") == "gan_topic"
    assert classify_idle_thought_type("[Self-thought] xxx") == "gan_synthesis"
    assert classify_idle_thought_type("[Idle Activity] chooses: 3") == "gan"
    assert classify_idle_thought_type("[Self-Optimization] x") == "solve_mode"
    assert classify_idle_thought_type("普通思考") == "internal"
    # 帶顯式類型原樣保留
    assert classify_idle_thought_type("[Social] x", "gan_argument") == "gan_argument"


def test_event_bus_pub_sub_and_history():
    bus = _idle_event_bus
    # 先訂閱再發布，避免同進程其他測試留下的歷史事件干擾長度斷言
    q, recent = bus.subscribe()
    try:
        assert isinstance(recent, list)
        base_seq = recent[-1]["seq"] if recent else 0

        publish_engine_event({"type": "internal_thought",
                              "thought": "[Social] 第一條社交思考"})
        publish_engine_event({"type": "error", "error": "boom"})
        publish_engine_event({"type": "autonomous_message", "message": "找主人"})
        publish_engine_event({"type": "internal_thought", "thought_type": "gan_topic",
                              "thought": "[Gan Topic] 帶類型"})

        events = [q.get(timeout=2) for _ in range(4)]
        assert [e["seq"] for e in events] == [base_seq + 1, base_seq + 2,
                                              base_seq + 3, base_seq + 4]
        assert events[0]["thought_type"] == "social"
        assert events[1]["type"] == "error" and events[1]["content"] == "boom"
        assert events[2]["type"] == "autonomous"
        assert events[3]["thought_type"] == "gan_topic"

        # 歷史緩衝裡同樣保留這四條
        q2, hist = bus.subscribe()
        bus.unsubscribe(q2)
        tail = hist[-4:]
        assert [e["seq"] for e in tail] == [e["seq"] for e in events]

        # 非字典 / 空內容安全忽略（不應產生事件）
        publish_engine_event(None)
        publish_engine_event({"type": "internal_thought", "thought": ""})
        assert q.empty()
    finally:
        bus.unsubscribe(q)


def test_skills_dir_and_manager():
    skills_dir = _resolve_skills_dir()
    assert skills_dir and os.path.isdir(skills_dir), skills_dir
    mgr = _get_skills_manager()
    names = {s.name for s in mgr.get_all_skills()}
    assert "misskey-bot" in names, f"misskey-bot 未載入: {names}"
    mk = mgr.get_skill("misskey-bot")
    assert mk.executor is not None, "misskey-bot 缺少 executor"
    assert mk.to_dict()["name"] == "misskey-bot"


def test_execute_whitelist():
    assert _SKILL_EXECUTE_WHITELIST["misskey-bot"] == {"status", "configure", "set_bot"}
    assert "shell" not in _SKILL_EXECUTE_WHITELIST


def test_misskey_status_action():
    mgr = _get_skills_manager()
    res = mgr.execute_skill("misskey-bot", {"action": "status"}, language="zh-TW")
    assert isinstance(res, dict) and "has_token" in res, res
    assert "token" not in res, "status 不得回傳 token"
