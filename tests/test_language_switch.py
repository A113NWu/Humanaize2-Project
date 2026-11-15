# -*- coding: utf-8 -*-
"""语言切换测试：口头换语言识别、回复语言指令块、规则 v3 迁移、TTS 默认音色。"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "src", "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

import thinking_engine_api as api  # noqa: E402
from core.data import causal_rules as cr  # noqa: E402
from core.voice import tts_synthesizer as tts  # noqa: E402


# ---------------------------------------------------------------------------
# 口头换语言识别
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("用英文回复我", "English"),
    ("说英语", "English"),
    ("换成英文", "English"),
    ("switch to English", "English"),
    ("speak english", "English"),
    ("用中文跟我聊", "中文"),
    ("说汉语", "中文"),
    ("切换成中文", "中文"),
    ("speak Chinese", "中文"),
    ("今天天气怎么样", None),
    ("帮我把这段话翻译成英文然后念出来", None),  # 「翻译成英文」是翻译任务，不是换语言指令
])
def test_detect_language_switch(text, expected):
    assert api._detect_language_switch(text) == expected


def test_detect_language_switch_ignores_empty():
    assert api._detect_language_switch("") is None
    assert api._detect_language_switch(None) is None


# ---------------------------------------------------------------------------
# 回复语言指令块
# ---------------------------------------------------------------------------
@pytest.fixture()
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "ui_settings.json"
    monkeypatch.setattr(api, "get_settings_path", lambda: str(path))
    return path


def test_language_block_follows_settings(settings_file):
    settings_file.write_text(json.dumps({"language": "English"}), encoding="utf-8")
    assert api._reply_language() == "en"
    assert "English" in api._language_instruction_block()

    settings_file.write_text(json.dumps({"language": "中文"}), encoding="utf-8")
    assert api._reply_language() == "zh"
    assert "中文" in api._language_instruction_block()


def test_language_block_defaults_to_chinese(settings_file):
    assert api._reply_language() == "zh"


# ---------------------------------------------------------------------------
# 口头换语言持久化
# ---------------------------------------------------------------------------
def test_apply_language_switch_persists(settings_file, monkeypatch):
    settings_file.write_text(json.dumps({"language": "中文", "theme": "Liquid Glass"}),
                             encoding="utf-8")

    calls = []

    class FakeEngine:
        def set_language(self, lang):
            calls.append(lang)

    api._apply_language_switch("English", FakeEngine())
    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["language"] == "English"
    assert saved["theme"] == "Liquid Glass"  # 其它设置不丢
    assert calls == ["en"]

    api._apply_language_switch("中文", FakeEngine())
    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["language"] == "中文"
    assert calls[-1] == "zh"


# ---------------------------------------------------------------------------
# 因果规则 v3 迁移：旧「固定中文」规则就地替换
# ---------------------------------------------------------------------------
@pytest.fixture()
def rules(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "DATA_DIR", str(tmp_path))
    return cr


def _write_rules_file(rules_mod, rule_dicts, seed_ver):
    path = os.path.join(rules_mod.DATA_DIR, "causal_rules.json")
    os.makedirs(rules_mod.DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "seed_ver": seed_ver,
                   "rules": rule_dicts, "updated_at": 0}, f, ensure_ascii=False)


def test_seed_v3_replaces_old_language_rule(rules):
    old = rules._make_rule("主人看不懂其他语言，你一直用中文和他说话",
                           "用中文回复；主人主动换语言时再跟着换")
    _write_rules_file(rules, [old], seed_ver=2)
    data = rules._load()
    migrated = [r for r in data["rules"] if r["id"] == old["id"]]
    assert len(migrated) == 1
    assert migrated[0]["cause"] == rules._NEW_LANG_CAUSE
    assert migrated[0]["text"] == rules.normalize_rule(rules._NEW_LANG_CAUSE,
                                                       rules._NEW_LANG_ACTION)
    assert data["seed_ver"] == rules._SEED_VER


def test_seed_v3_keeps_user_edited_language_rule(rules):
    edited = rules._make_rule("主人让我用什么语言就用什么语言", "跟主人保持一致")
    _write_rules_file(rules, [edited], seed_ver=2)
    data = rules._load()
    kept = [r for r in data["rules"] if r["id"] == edited["id"]]
    assert kept and kept[0]["cause"] == "主人让我用什么语言就用什么语言"


def test_seed_v3_migration_idempotent(rules):
    old = rules._make_rule("主人看不懂其他语言，你一直用中文和他说话",
                           "用中文回复；主人主动换语言时再跟着换")
    _write_rules_file(rules, [old], seed_ver=2)
    first = rules._load()
    second = rules._load()
    assert len(first["rules"]) == len(second["rules"])
    # 新语言规则不重复出现
    texts = [r["text"] for r in second["rules"]]
    new_text = rules.normalize_rule(rules._NEW_LANG_CAUSE, rules._NEW_LANG_ACTION)
    assert texts.count(new_text) == 1


# ---------------------------------------------------------------------------
# TTS 默认音色跟随语种
# ---------------------------------------------------------------------------
def test_tts_default_voice_by_language():
    assert tts._default_voice_for_text("kokoro", "Hello, how are you today?") == "af_heart"
    assert tts._default_voice_for_text("kokoro", "你好呀，今天过得怎么样？") == "zf_001"
    assert tts._default_voice_for_text("edge_tts", "Hello, how are you today?") == "en-US-AriaNeural"
    assert tts._default_voice_for_text("edge_tts", "你好呀，今天过得怎么样？") == "zh-CN-XiaoxiaoNeural"


# ---------------------------------------------------------------------------
# [motion:...] 动作标签剥离
# ---------------------------------------------------------------------------
from core.thinking_engine import ThinkingEngine  # noqa: E402


@pytest.mark.parametrize("raw,expected_text,expected_motions", [
    ("你好呀 [motion:Idle 0] 今天过得怎么样", "你好呀 今天过得怎么样", [("Idle", 0)]),
    ("早上好[motion：Idle：3]！", "早上好！", [("Idle", 3)]),
    ("嘿 [motion:tap_body-1] 来玩吧", "嘿 来玩吧", [("tap_body-1", None)]),  # 连字符属于组名，编号只认冒号/空格分隔
    ("看这个 [motion:TapBody 0] 厉害吧 [motion:Idle]", "看这个 厉害吧", [("TapBody", 0), ("Idle", None)]),
    ("没有动作标签", "没有动作标签", []),
])
def test_extract_motion_tags_variants(raw, expected_text, expected_motions):
    cleaned, motions = ThinkingEngine._extract_motion_tags(raw)
    assert expected_text in cleaned
    assert "[" not in cleaned and "]" not in cleaned
    assert motions == expected_motions


def test_api_motion_regex_strips_stream_chunks():
    content = "好的 [motion:TapBody 0] 没问题[motion：Idle：2]"
    out = api._MOTION_TAG_RE.sub("", content)
    assert "motion" not in out.lower() and "[" not in out and "]" not in out
    assert "好的" in out and "没问题" in out
