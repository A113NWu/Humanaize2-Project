"""
Misskey 新消息 / 活動監聽器

後台線程定期輪詢 Misskey：有新提及或本地時間線新動態時提醒 Aize，
由她自己決定是否互動（reply / react 二選一，或 post 發新動態，或 ignore）。
所有對外文本經敏感詞過濾；決策與執行結果以 internal_thought(social) 事件
推給 UI（CLI 因果樹 / 網頁思考面板）。
"""

import os
import re
import sys
import json
import time
import threading

_DEFAULT_INTERVAL = 120          # 秒
_MAX_ITEMS_PER_POLL = 5          # 每次輪詢最多交給 Aize 決策的條目
_SEEN_CAP = 300


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _settings():
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["get_settings_path"])
            return _load_json(m.get_settings_path(), {})
        except Exception:
            continue
    return {}


def _data_dir():
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            return m.app_data_dir()
        except Exception:
            continue
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_skill_module(skill_name):
    """以文件路徑隔離載入技能模塊（兼容 dev 與打包態）。"""
    import importlib.util
    here = os.path.abspath(__file__)                      # src/core/tools/
    roots = [
        os.path.dirname(os.path.dirname(os.path.dirname(here))),      # src
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here)))),  # 項目根
    ]
    if getattr(sys, "frozen", False):
        roots.insert(0, os.path.dirname(sys.executable))
    candidates = [os.path.join(r, "skills", skill_name, "__init__.py") for r in roots]
    for init in candidates:
        if not os.path.exists(init):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"skills_{skill_name.replace('-', '_')}", init)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            continue
    return None


def _chat(prompt, max_tokens=400, timeout=60):
    for mod in ("llm", "core.llm"):
        try:
            m = __import__(mod, fromlist=["chat"])
            return m.chat(prompt, max_tokens=max_tokens, timeout=timeout)
        except Exception:
            continue
    return ""


def _load_prompt(name):
    for mod in ("core.data.prompts_manager", "data.prompts_manager"):
        try:
            m = __import__(mod, fromlist=["load_prompt"])
            return m.load_prompt(name)
        except Exception:
            continue
    return ""


def _filter_check(text):
    for mod in ("core.tools.content_filter", "tools.content_filter"):
        try:
            m = __import__(mod, fromlist=["check"])
            return m.check(text)
        except Exception:
            continue
    return True, []


class MisskeyWatcher:
    """輪詢 Misskey，發現新消息/活動時提醒 Aize 並由她決定互動與否。"""

    def __init__(self, on_event=None):
        self.on_event = on_event
        self.running = True
        self._first_poll = True
        self._seen = []
        self._state_path = os.path.join(_data_dir(), "misskey_watch_state.json")
        self._seen = _load_json(self._state_path, {}).get("seen", [])
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False

    # ---------- 事件 ----------

    def _emit(self, text):
        if self.on_event:
            try:
                self.on_event({"type": "internal_thought",
                               "thought": f"[Misskey] {text}",
                               "thought_type": "social"})
            except Exception:
                pass

    # ---------- 主循環 ----------

    def _run(self):
        time.sleep(30)  # 啟動寬限：等網絡/配置就緒
        while self.running:
            interval = _DEFAULT_INTERVAL
            try:
                cfg = _settings()
                if cfg.get("misskey_watch_enabled", True):
                    interval = max(30, int(cfg.get("misskey_watch_interval", _DEFAULT_INTERVAL)))
                    self._poll_once()
            except Exception as e:
                self._emit(f"輪詢出錯：{e}")
            slept = 0
            while self.running and slept < interval:
                time.sleep(5)
                slept += 5

    def _poll_once(self):
        mod = _load_skill_module("misskey-bot")
        if mod is None:
            return
        bot = mod._get_bot()
        if not bot.config.get("token"):
            return

        items = []  # (kind, note_id, user, text)
        try:
            r = bot.mentions(limit=5)
            if r.get("success"):
                for n in (r.get("mentions") or []):
                    items.append(("提及", str(n.get("id") or ""),
                                  str(n.get("user") or "?"), str(n.get("text") or "")))
        except Exception:
            pass
        try:
            r = bot.timeline("local", limit=5)
            if r.get("success"):
                for n in (r.get("notes") or []):
                    items.append(("動態", str(n.get("id") or ""),
                                  str(n.get("user") or "?"), str(n.get("text") or "")))
        except Exception:
            pass

        fresh, seen_changed = [], False
        for kind, nid, user, text in items:
            if not nid:
                continue
            if nid not in self._seen:
                fresh.append((kind, nid, user, text))
                self._seen.append(nid)
                seen_changed = True
        if seen_changed:
            self._seen = self._seen[-_SEEN_CAP:]
            _save_json(self._state_path, {"seen": self._seen})

        if self._first_poll:
            # 首輪只記錄現狀，不對歷史消息批量決策
            self._first_poll = False
            return
        if not fresh:
            return

        fresh = fresh[:_MAX_ITEMS_PER_POLL]
        mention_cnt = sum(1 for k, *_ in fresh if k == "提及")
        self._emit(f"收到 {len(fresh)} 條新消息/活動（其中 {mention_cnt} 條提及），Aize 正在決定是否互動…")
        self._decide_and_act(bot, fresh)

    # ---------- 決策與執行 ----------

    def _decide_and_act(self, bot, fresh):
        base = _load_prompt("misskey_interact")
        if not base:
            self._emit("決策提示詞 misskey_interact 缺失，本次跳過")
            return
        lines = [f"[{nid}]（{kind}）@{user}: {text[:160]}" for kind, nid, user, text in fresh]
        prompt = (base.replace("{host}", str(bot.config.get("host") or "Misskey"))
                      .replace("{items}", "\n".join(lines)))
        raw = _chat(prompt, max_tokens=500, timeout=60)
        actions = self._parse_actions(raw)
        if actions is None:
            self._emit("沒看懂 Aize 的決定（輸出不是有效 JSON），本次忽略")
            return

        acted = 0
        posted = False
        for act in actions:
            if not isinstance(act, dict):
                continue
            atype = str(act.get("action", "")).strip().lower()
            nid = str(act.get("note_id", "")).strip()

            if atype == "ignore" or not atype:
                continue

            if atype == "react":
                target = nid or (fresh[0][1] if fresh else "")
                reaction = str(act.get("reaction", "👍")).strip() or "👍"
                r = bot.react(target, reaction)
                if r.get("success"):
                    acted += 1
                    self._emit(f"Aize 給帖子 {target} 點了 {reaction}")
                else:
                    self._emit(f"點表情失敗（{reaction}）：{r.get('error')}")

            elif atype == "reply":
                text = str(act.get("text", "")).strip()
                if not text or not nid:
                    continue
                ok, hits = _filter_check(text)
                if not ok:
                    self._emit(f"Aize 的回覆被過濾器攔截（{len(hits)} 個敏感詞），未發送")
                    continue
                r = bot.post(text, reply_id=nid)
                if r.get("success"):
                    acted += 1
                    self._emit(f"Aize 回覆了 @{self._user_of(fresh, nid)}：{text[:60]}")
                else:
                    self._emit(f"回覆失敗：{r.get('error')}")

            elif atype == "post":
                if posted:
                    continue
                text = str(act.get("text", "")).strip()
                if not text:
                    continue
                ok, hits = _filter_check(text)
                if not ok:
                    self._emit(f"Aize 的新動態被過濾器攔截（{len(hits)} 個敏感詞），未發佈")
                    continue
                r = bot.post(text)
                if r.get("success"):
                    acted += 1
                    posted = True
                    self._emit(f"Aize 發佈了新動態：{text[:60]}（{r.get('url', '')}）")
                else:
                    self._emit(f"發佈失敗：{r.get('error')}")

        if acted == 0:
            self._emit("Aize 看了一圈，決定都不互動（忽略）")

    @staticmethod
    def _user_of(fresh, nid):
        for _kind, i, user, _text in fresh:
            if i == nid:
                return user
        return "?"

    @staticmethod
    def _parse_actions(raw):
        """從 Aize 輸出提取 {"actions":[...]}；失敗返回 None。"""
        m = re.search(r"\{.*\}", (raw or "").strip(), re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
        acts = data.get("actions")
        return acts if isinstance(acts, list) else None
