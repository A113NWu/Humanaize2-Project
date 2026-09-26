# -*- coding: utf-8 -*-
"""網頁事件匯流排 + 技能管理 API 的冒煙測試（不需 LLM / 網路）。"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "core"))

from thinking_engine_api import (
    IdleEventBus, publish_engine_event, classify_idle_thought_type,
    _get_skills_manager, _resolve_skills_dir, _SKILL_EXECUTE_WHITELIST,
    _idle_event_bus,
)

# 1) 思考類型分類
assert classify_idle_thought_type("[Social] Aize 選擇去逛逛") == "social"
assert classify_idle_thought_type("[Thinking Direction] AI") == "gan_topic"
assert classify_idle_thought_type("[Self-thought] xxx") == "gan_synthesis"
assert classify_idle_thought_type("[Idle Activity] chooses: 3") == "gan"
assert classify_idle_thought_type("[Self-Optimization] x") == "solve_mode"
assert classify_idle_thought_type("普通思考") == "internal"
# 帶顯式類型原樣保留
assert classify_idle_thought_type("[Social] x", "gan_argument") == "gan_argument"
print("classify: PASS")

# 2) 事件匯流排：訂閱、補發歷史、seq 去重（使用模組級單例）
bus = _idle_event_bus
publish_engine_event({"type": "internal_thought",
                      "thought": "[Social] 第一條社交思考"})
publish_engine_event({"type": "error", "error": "boom"})
publish_engine_event({"type": "autonomous_message", "message": "找主人"})
publish_engine_event({"type": "internal_thought", "thought_type": "gan_topic",
                      "thought": "[Gan Topic] 帶類型"})
q, recent = bus.subscribe()
assert len(recent) == 4, recent
assert recent[0]["seq"] == 1 and recent[-1]["seq"] == 4
assert recent[0]["thought_type"] == "social"
assert recent[1]["type"] == "error" and recent[1]["content"] == "boom"
assert recent[2]["type"] == "autonomous"
assert recent[3]["thought_type"] == "gan_topic"
# 新事件實時送達訂閱者
publish_engine_event({"type": "internal_thought", "thought": "再一條即時"})
ev = q.get(timeout=2)
assert ev["content"] == "再一條即時" and ev["seq"] == 5
# 非字典 / 空內容安全忽略
publish_engine_event(None)
publish_engine_event({"type": "internal_thought", "thought": ""})
print("event bus: PASS")

# 3) 技能目錄解析 + 管理器列出技能
skills_dir = _resolve_skills_dir()
assert skills_dir and os.path.isdir(skills_dir), skills_dir
mgr = _get_skills_manager()
names = {s.name for s in mgr.get_all_skills()}
assert "misskey-bot" in names, f"misskey-bot 未載入: {names}"
mk = mgr.get_skill("misskey-bot")
assert mk.executor is not None, "misskey-bot 缺少 executor"
assert mk.to_dict()["name"] == "misskey-bot"
print(f"skills dir = {skills_dir}")
print(f"skills({len(names)}): {sorted(names)}")

# 4) 網頁執行白名單：只允許 misskey-bot 安全動作
assert _SKILL_EXECUTE_WHITELIST["misskey-bot"] == {"status", "configure", "set_bot"}
assert "shell" not in _SKILL_EXECUTE_WHITELIST
print("execute whitelist: PASS")

# 5) misskey status 動作可執行（未配置 token 也應返回結構化結果，不報異常）
res = mgr.execute_skill("misskey-bot", {"action": "status"}, language="zh-TW")
assert isinstance(res, dict) and "has_token" in res, res
assert "token" not in res, "status 不得回傳 token"
print(f"misskey status ok: has_token={res['has_token']}")

print("ALL TESTS PASSED")
