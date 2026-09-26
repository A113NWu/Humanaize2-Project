# -*- coding: utf-8 -*-
"""真實 HTTP 層驗證：/api/skills、/api/skills/toggle、/api/skills/execute、/api/events。"""
import json
import os
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "core"))

from thinking_engine_api import ThinkingEngineAPIServer, publish_engine_event

PORT = 18099
BASE = f"http://127.0.0.1:{PORT}"
server = ThinkingEngineAPIServer("127.0.0.1", PORT)
server.start()
time.sleep(0.5)


def get(path, timeout=60):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# 1) GET /api/skills
st, body, _ = get("/api/skills")
assert st == 200
data = json.loads(body)
names = [s["name"] for s in data["skills"]]
assert "misskey-bot" in names
print(f"GET /api/skills -> 200, {len(names)} skills")

# 2) 白名單：shell 必須 403
st, body = post("/api/skills/execute",
                {"name": "shell", "action": "execute", "params": {"command": "whoami"}})
assert st == 403, st
print("POST /api/skills/execute shell -> 403 OK")

# 3) misskey status
st, body = post("/api/skills/execute", {"name": "misskey-bot", "action": "status"})
assert st == 200 and body["result"].get("success") is True, body
print("POST misskey status -> 200 OK")

# 4) toggle 一個無害技能（reddit）然後恢復
st, body = post("/api/skills/toggle", {"name": "reddit", "enabled": False})
assert st == 200 and body["enabled"] is False
reddit = [s for s in body["skills"] if s["name"] == "reddit"][0]
assert reddit["enabled"] is False
st, body = post("/api/skills/toggle", {"name": "reddit", "enabled": True})
assert st == 200 and body["enabled"] is True
print("toggle reddit false->true OK")

# 5) SSE：先連線，再從進程內發事件，應在流上收到
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
assert "raw" in sse_payload, sse_payload
assert '"thought_type": "social"' in sse_payload["raw"] or '"thought_type":"social"' in sse_payload["raw"]
print("GET /api/events delivered live event OK")

server.stop()
print("ALL HTTP TESTS PASSED")
