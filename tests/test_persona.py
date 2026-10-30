# -*- coding: utf-8 -*-
"""統一 Aize 人格/習慣/情緒模塊的離線單元測試（不聯網、不調 LLM）。"""
import os
import sys
from datetime import datetime, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src", "core") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src", "core"))

import persona


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """把所有数据文件隔离到 tmp_path。"""
    monkeypatch.setattr(persona, "_data_dir", lambda: str(tmp_path))
    return tmp_path


def _fake_memory(text="我要上课了"):
    return {"messages": [{
        "role": "user",
        "content": text,
        "time": datetime.now().isoformat(),
    }]}


def test_note_user_message_detects_absence_and_suppresses():
    memory = _fake_memory("我要上课了")
    persona.note_user_message(memory, "我要上课了")

    status = persona.habit_status()
    assert status["awaiting"]["kind"] == "上课"
    assert status["awaiting"]["expected_return_at"]

    assert persona.suppression_until() is not None
    assert persona.habit_is_active() is True


def test_next_message_settles_interval_into_patterns():
    memory = _fake_memory("我要上课了")
    persona.note_user_message(memory, "我要上课了")

    # 把离开时间改到 40 分钟前，模拟主人 40 分钟后回来
    habits = persona._load_json("user_habits.json", {})
    habits["awaiting"]["at"] = (datetime.now() - timedelta(minutes=40)).isoformat()
    habits["awaiting"]["expected_return_at"] = (datetime.now() + timedelta(minutes=5)).isoformat()
    persona._save_json("user_habits.json", habits)

    persona.note_user_message(memory, "我回来了")

    status = persona.habit_status()
    assert status["awaiting"] is None
    item = status["patterns"]["上课"]
    assert item["count"] == 1
    assert 39 <= item["avg_minutes"] <= 41


def test_learn_emotion_dedup_and_cap():
    for i in range(510):
        assert persona.learn_emotion(f"样本文字{i}", f"情绪{i % 12}") is True

    learned = persona.list_emotions()["learned"]
    assert len(learned) <= persona.LEARNED_EMOTION_MAX

    assert persona.learn_emotion("重复样例", "喜悦") is True
    assert persona.learn_emotion("重复样例", "喜悦") is False
    duplicate = [e for e in persona.list_emotions()["learned"] if e.get("text") == "重复样例"]
    assert len(duplicate) == 1


def test_compose_prompt_puts_base_before_persona():
    out = persona.compose_prompt_with_persona("用户自定义提示词：你是 Aize。", "chat")
    assert out.startswith("用户自定义提示词：你是 Aize。")
    assert out.index("用户自定义提示词：你是 Aize。") < out.index("【Aize 的自我人格】")


def test_persona_block_has_time_and_gap():
    memory = {"messages": [{
        "role": "user",
        "content": "你好",
        "time": (datetime.now() - timedelta(minutes=30)).isoformat(),
    }]}
    block = persona.persona_block("chat", memory)

    assert "【此刻】" in block
    assert "距上次主人说话" in block
    assert "30 分钟" in block
    assert len(block) < 1500
