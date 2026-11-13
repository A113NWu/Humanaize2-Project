# -*- coding: utf-8 -*-
"""因果规则表测试：句式校验、匹配、注入、迭代与举一反三。"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "src", "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from core.data import causal_rules as cr  # noqa: E402


@pytest.fixture()
def rules(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "DATA_DIR", str(tmp_path))
    return cr


def _seed_texts(rules):
    return [r["text"] for r in rules.list_rules()]


def test_seed_rules_follow_causal_format(rules):
    texts = _seed_texts(rules)
    assert len(texts) >= 6
    for text in texts:
        assert text.startswith("因为")
        assert "，所以你要" in text
        ok, err = rules.validate_rule(text)
        assert ok, f"{text} -> {err}"


def test_growth_rule_is_optional_not_mandatory(rules):
    growth = next(r for r in rules.list_rules() if r.get("optional"))
    assert "成长" in growth["cause"]
    assert "因为……所以……" in growth["action"]
    assert growth.get("mandatory") is False
    assert "可选" in rules.prompt_block("我想上网找点规律")


@pytest.mark.parametrize("text", [
    "因为主人很晚还没有休息，所以你要提醒主人早点睡",
    "因为主人很晚还没有休息,所以你要提醒主人早点睡",
    "因为主人很晚还没有休息，所以要你提醒主人早点睡。",
])
def test_validate_accepts_common_variants(rules, text):
    ok, err = rules.validate_rule(text)
    assert ok, err


@pytest.mark.parametrize("text", [
    "",
    "主人很晚还没有休息",
    "因为 所以你要",
    "因为主人很晚还没有休息，所以我该提醒他",
])
def test_validate_rejects_malformed(rules, text):
    ok, _ = rules.validate_rule(text)
    assert not ok


def test_add_rule_dedupes_and_bumps_confidence(rules):
    text = "因为主人在赶进度，所以你要少打扰、只在必要时提醒"
    first = rules.add_rule(text, source="self", confidence=0.4)
    second = rules.add_rule(text, source="self", confidence=0.4)
    assert first["success"] and second["success"]
    assert second["duplicate"] is True
    assert second["rule"]["id"] == first["rule"]["id"]
    assert second["rule"]["confidence"] > first["rule"]["confidence"]
    assert len([r for r in rules.list_rules() if r["text"] == text]) == 1


def test_search_matches_scenario(rules):
    assert "深夜" in rules.search("今天好困，想早点睡")[0]["rule"]["text"] or \
           "晚还没有休息" in rules.search("今天好困，想早点睡")[0]["rule"]["text"]

    sad = rules.search("我今天特别难过，想找人说说话")
    assert sad and "难过" in sad[0]["rule"]["cause"]

    leaving = rules.search("我一会儿要出门了")
    assert leaving and "出门" in leaving[0]["rule"]["cause"]


def test_search_generalizes_to_unseen_phrasing(rules):
    """举一反三：没有出现关键词原词，也要能匹配到正确规则。"""
    matched = rules.search("都已经这个点了，我还没休息")
    assert matched
    top = matched[0]["rule"]["text"]
    assert "晚还没有休息" in top or "早点睡" in top


def test_prompt_block_contains_usage_contract(rules):
    block = rules.prompt_block("我一会儿要出门了")
    assert "因果规则表" in block
    assert "因为" in block and "所以你要" in block
    assert "不要复述规则原文" in block


def test_disable_excludes_from_search(rules):
    sleep_rule = next(r for r in rules.list_rules() if "晚还没有休息" in r["text"])
    assert rules.set_enabled(sleep_rule["id"], False) is True
    ids = [item["rule"]["id"] for item in rules.search("好困想睡了", top_k=10)]
    assert sleep_rule["id"] not in ids
    rules.set_enabled(sleep_rule["id"], True)


def test_feedback_adjusts_confidence(rules):
    rule = rules.list_rules()[0]
    before = rule["confidence"]
    rules.record_feedback(rule["id"], True)
    after_up = next(r for r in rules.list_rules() if r["id"] == rule["id"])["confidence"]
    assert after_up > before
    rules.record_feedback(rule["id"], False)
    after_down = next(r for r in rules.list_rules() if r["id"] == rule["id"])["confidence"]
    assert after_down < after_up


def test_harvest_extracts_candidates_without_writing(rules):
    text = (
        "网上看到一句：因为主人害怕黑，所以你要在晚上留一盏小灯。"
        "另一句不符合格式：因为他喜欢猫。"
        "还有：因为 Aize 会忘事，所以要你把重要的事记下来。"
    )
    before = len(rules.list_rules())
    candidates = rules.harvest_candidates(text)
    assert len(candidates) == 2
    assert len(rules.list_rules()) == before
    assert all(c["text"].startswith("因为") for c in candidates)


def test_stats_reports_learned_rules(rules):
    rules.add_rule("因为主人在写代码，所以你要先给结论再给细节", source="self")
    info = rules.stats()
    assert info["learned"] >= 1
    assert info["enabled"] >= 1


def test_mark_used_counts_hits(rules):
    rule = rules.list_rules()[0]
    rules.mark_used([rule["id"]])
    assert next(r for r in rules.list_rules() if r["id"] == rule["id"])["hits"] == 1
