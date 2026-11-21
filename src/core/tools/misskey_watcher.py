"""
Misskey 新消息 / 活動監聽器

後台線程定期輪詢 Misskey：有新提及或本地時間線新動態時，只把消息放進
social_inbox 收件匣並推一個 internal_thought(social) 事件提醒 UI。
是否回應由 Aize 在閒置思考 / 對話的猶豫環節自己決定（reply / react / 忽略）。
"""

import os
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


def _short_term():
    """短期記憶模塊（收到的消息先放進去，再由她自己判斷是否進長期）。"""
    for mod in ("memory.short_term", "core.memory.short_term"):
        try:
            return __import__(mod, fromlist=["record_turn"])
        except Exception:
            continue
    return None


class MisskeyWatcher:
    """輪詢 Misskey，發現新消息/活動時放進收件匣提醒 Aize。"""

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
                # 技能被停用時完全不輪詢，避免停用後仍自動互動
                try:
                    from tools.skills_manager import is_skill_enabled
                except ImportError:
                    from core.tools.skills_manager import is_skill_enabled
                if cfg.get("misskey_watch_enabled", True) and is_skill_enabled("misskey-bot"):
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
        # 每條提及先寫進短期記憶：回不回由她決定，是否值得長期記住也由她判斷
        st = _short_term()
        if st:
            for kind, _nid, user, text in fresh:
                if kind != "提及":
                    continue
                try:
                    st.record_turn(f"@{user}：{text}", source="misskey",
                                   speaker=f"@{user}（Misskey）")
                except Exception:
                    pass
        # 監聽器不再自己決定回不回：只把新消息放進收件匣，
        # 等 Aize 在閒置思考或對話中自己猶豫、掂量要不要回應。
        added = 0
        try:
            try:
                from tools import social_inbox
            except ImportError:
                from core.tools import social_inbox
            for kind, nid, user, text in fresh:
                if social_inbox.push("misskey", kind, nid, user, text):
                    added += 1
        except Exception as e:
            self._emit(f"放入待處理收件匣失敗：{e}")
            return

        mention_cnt = sum(1 for k, *_ in fresh if k == "提及")
        if added:
            self._emit(f"收到 {len(fresh)} 條新消息/活動（其中 {mention_cnt} 條提及），"
                       f"{added} 條已放入待處理收件匣，等 Aize 自己判斷要不要回應")
        else:
            self._emit("收到的新消息都已在待處理收件匣裡，跳過重複提醒")
