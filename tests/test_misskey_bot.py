"""Misskey 機器人 + 內容過濾器單元測試（不聯網）。"""
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(ROOT, "src", "core") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src", "core"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_content_filter(tmp_path, monkeypatch):
    import tools.content_filter as cf
    words_file = tmp_path / "words.txt"
    words_file.write_text("# comment\n\nfoobar\nABC\n", encoding="utf-8")
    monkeypatch.setenv("HUMANAIZE_SENSITIVE_WORDS", str(words_file))
    cf._LOADED_PATH = None  # 強制重載
    return cf, words_file


def _load_misskey_module():
    init = os.path.join(ROOT, "skills", "misskey-bot", "__init__.py")
    spec = importlib.util.spec_from_file_location("skills_misskey_bot", init)
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    return mk


def test_content_filter(tmp_path, monkeypatch):
    cf, words_file = _load_content_filter(tmp_path, monkeypatch)

    assert cf.check("今天天氣真好") == (True, [])
    ok, hits = cf.check("這是FooBar測試")
    assert not ok and "foobar" in hits, hits
    ok, hits = cf.check("abc 大寫測試")
    assert not ok and "abc" in hits, hits
    assert cf.sanitize("abc和foobar") == "***和***", cf.sanitize("abc和foobar")

    # 熱更新：改文件後新增詞生效
    with open(words_file, "a", encoding="utf-8") as f:
        f.write("新敏感\n")
    ok, _ = cf.check("含新敏感词的句子")
    assert not ok, "熱更新失敗"


def test_misskey_skill_actions(tmp_path, monkeypatch):
    cf, words_file = _load_content_filter(tmp_path, monkeypatch)
    mk = _load_misskey_module()

    # 無效 action
    r = mk.execute({"action": "nope"})
    assert r["success"] is False and "未知動作" in r["error"], r

    # 無 token 不能發（先清空，避免讀到本機已保存的 token 而真的發請求）
    bot = mk._get_bot()
    bot.config["token"] = ""
    r = mk.execute({"action": "post", "params": {"text": "hello"}})
    assert r["success"] is False and "token" in r["error"], r

    # 空內容
    bot.config["token"] = "fake"
    r = mk.execute({"action": "post", "params": {"text": "  "}})
    assert r["success"] is False and "空" in r["error"], r

    # reply 缺 id
    r = mk.execute({"action": "reply", "params": {"text": "hi"}})
    assert r["success"] is False and "reply_id" in r["error"], r

    # configure 去協議前綴
    r = bot.configure({"host": "https://hub.imikufans.com/", "token": ""})
    assert bot.config["host"] == "hub.imikufans.com", bot.config["host"]
    bot.config["token"] = "fake"

    # 敏感詞攔截（不應發起網絡請求）
    with open(words_file, "w", encoding="utf-8") as f:
        f.write("禁詞X\n")
    cf._LOADED_PATH = None
    r = mk.execute({"action": "post", "params": {"text": "這條含禁詞X應被擋"}})
    assert r["success"] is False and "過濾" in r["error"], r
