# -*- coding: utf-8 -*-
"""真實 HTTP 層驗證：/api/skills、/api/skills/toggle、/api/skills/execute、/api/events。"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src", "core") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src", "core"))

from thinking_engine_api import ThinkingEngineAPIServer, publish_engine_event

PORT = 18099
BASE = f"http://127.0.0.1:{PORT}"


def _get(path, timeout=60):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore"), dict(e.headers)


def _require_no_auth(status):
    if status == 401:
        pytest.skip("API 已啟用登入憑證，跳過未認證的 HTTP 測試")


def _post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


@pytest.fixture(scope="module")
def server():
    srv = ThinkingEngineAPIServer("127.0.0.1", PORT)
    srv.start()
    time.sleep(0.5)
    yield srv
    srv.stop()


def test_list_skills(server):
    st, body, _ = _get("/api/skills")
    _require_no_auth(st)
    assert st == 200
    data = json.loads(body)
    names = [s["name"] for s in data["skills"]]
    assert "misskey-bot" in names


def test_shell_execute_forbidden(server):
    st, _ = _post("/api/skills/execute",
                  {"name": "shell", "action": "execute", "params": {"command": "whoami"}})
    _require_no_auth(st)
    assert st == 403, st


def test_misskey_status(server):
    st, body = _post("/api/skills/execute", {"name": "misskey-bot", "action": "status"})
    _require_no_auth(st)
    assert st == 200 and body["result"].get("success") is True, body


def test_toggle_skill_roundtrip(server):
    st, body = _post("/api/skills/toggle", {"name": "reddit", "enabled": False})
    _require_no_auth(st)
    assert st == 200 and body["enabled"] is False
    reddit = [s for s in body["skills"] if s["name"] == "reddit"][0]
    assert reddit["enabled"] is False
    st, body = _post("/api/skills/toggle", {"name": "reddit", "enabled": True})
    assert st == 200 and body["enabled"] is True


def test_causal_rules_dashboard_roundtrip(server, tmp_path, monkeypatch):
    from core.data import causal_rules as cr

    monkeypatch.setattr(cr, "DATA_DIR", str(tmp_path))
    st, body, _ = _get("/api/causal-rules")
    _require_no_auth(st)
    assert st == 200
    initial = json.loads(body)
    assert initial["ok"] is True and len(initial["rules"]) >= 6

    st, created = _post("/api/causal-rules", {
        "text": "因为主人在进行仪表盘验证，所以你要先确认规则已经保存",
        "keywords": ["仪表盘验证"], "optional": False,
    })
    assert st == 200 and created["ok"] is True, created
    rule_id = created["rule"]["id"]
    assert created["rule"]["source"] == "dashboard"

    st, updated = _post("/api/causal-rules", {
        "id": rule_id,
        "text": "因为主人正在检查规则编辑器，所以你要确认修改已经生效",
        "keywords": ["规则编辑器"], "optional": True, "enabled": True,
    })
    assert st == 200 and updated["rule"]["optional"] is True
    assert updated["rule"]["keywords"] == ["规则编辑器"]
    assert any(item["rule"]["id"] == rule_id
               for item in cr.search("我正在检查规则编辑器", top_k=10))

    st, invalid = _post("/api/causal-rules", {"id": rule_id, "text": "错误格式"})
    assert st == 400 and invalid["ok"] is False

    st, disabled = _post("/api/causal-rules", {"id": rule_id, "enabled": False})
    assert st == 200 and disabled["rule"]["enabled"] is False
    assert all(item["rule"]["id"] != rule_id
               for item in cr.search("我正在检查规则编辑器", top_k=10))

    st, removed = _post("/api/causal-rules", {"id": rule_id, "delete": True})
    assert st == 200 and removed["deleted"] is True
    assert all(item["id"] != rule_id for item in removed["rules"])

    mandatory = next(r for r in removed["rules"] if r.get("mandatory"))
    st, blocked = _post("/api/causal-rules", {"id": mandatory["id"], "delete": True})
    assert st == 400 and blocked["ok"] is False
    assert any(item["id"] == mandatory["id"]
               for item in cr.list_rules(include_disabled=True))


def test_sse_receives_live_event(server):
    sse_got = threading.Event()
    sse_payload = {}

    def read_sse():
        try:
            with urllib.request.urlopen(BASE + "/api/events", timeout=10) as r:
                buf = b""
                while not sse_got.is_set():
                    chunk = r.read(1)
                    if not chunk:
                        break
                    buf += chunk
                    text = buf.decode("utf-8", errors="ignore")
                    if "SSE_TEST_MARKER" in text:
                        sse_payload["raw"] = text
                        sse_got.set()
                        return
        except Exception as e:
            sse_payload["err"] = str(e)
            sse_got.set()

    t = threading.Thread(target=read_sse, daemon=True)
    t.start()
    time.sleep(1.0)
    publish_engine_event({"type": "internal_thought", "thought": "[Social] SSE_TEST_MARKER"})
    sse_got.wait(8)
    if "401" in str(sse_payload.get("err", "")):
        pytest.skip("API 已啟用登入憑證，跳過未認證的 SSE 測試")
    assert "raw" in sse_payload, sse_payload
    assert ('"thought_type": "social"' in sse_payload["raw"]
            or '"thought_type":"social"' in sse_payload["raw"])
