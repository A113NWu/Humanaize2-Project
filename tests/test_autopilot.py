# -*- coding: utf-8 -*-
"""Autopilot 逻辑测试：许可门禁、循环退出、状态写入、command/action 兼容。

不碰真实键鼠、不依赖本地模型：截图 / 视觉决策 / 动作执行全部用桩替换。
"""
import importlib.util
import os
import sys
import time as _time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "computer-control")
SKILL_PY = os.path.join(SKILL_DIR, "__init__.py")


def _load_skill():
    spec = importlib.util.spec_from_file_location("cc_autopilot_under_test", SKILL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _noop(*_args, **_kwargs):
    return None


def test_skill_description_mentions_autopilot():
    """提示词只注入技能名 + description，所以 Autopilot 必须出现在 description 里。"""
    with open(os.path.join(SKILL_DIR, "SKILL.md"), "r", encoding="utf-8") as f:
        text = f.read()
    front = text.split("---", 2)[1].lower()
    assert "autopilot" in front
    assert "autopilot_request" in front


def test_command_key_is_treated_as_action(monkeypatch, tmp_path):
    """模型按通用提示输出 {"command": ...} 时，应等价于 {"action": ...}。"""
    mod = _load_skill()
    monkeypatch.setattr(mod, "_enabled", lambda: True)
    monkeypatch.setattr(mod, "_screen_size", lambda: {"width": 100, "height": 100})
    shot = str(tmp_path / "shot.png")
    monkeypatch.setattr(mod, "_screenshot", lambda name="": shot)

    result = mod.execute({"command": "capture_screen"})
    assert result["success"] is True
    assert result["screenshot"] == shot


def test_unknown_command_returns_error(monkeypatch):
    """未知动作必须报错，不能静默返回 success（之前会误报“已开始接管”）。"""
    mod = _load_skill()
    monkeypatch.setattr(mod, "_enabled", lambda: True)
    monkeypatch.setattr(mod, "_clear_stop", _noop)
    monkeypatch.setattr(mod, "_check_stop", _noop)

    result = mod.execute({"command": "start"})
    assert result["success"] is False
    assert "未知 action" in result["error"]


def test_autopilot_requires_license(monkeypatch):
    """没有主人许可时 autopilot 必须被拒绝，并提示先申请。"""
    mod = _load_skill()
    monkeypatch.setattr(mod, "_enabled", lambda: True)
    monkeypatch.setattr(mod, "_licensed", lambda: False)

    result = mod.execute({"action": "autopilot"})
    assert result["success"] is False
    assert "许可" in result["error"]


def test_autopilot_loop_runs_steps_then_quit(monkeypatch):
    """有许可时：执行动作 → 写运行状态 → 输出 quit → 清状态并吊销许可。"""
    mod = _load_skill()
    monkeypatch.setattr(mod, "_enabled", lambda: True)
    monkeypatch.setattr(mod, "_licensed", lambda: True)
    monkeypatch.setattr(mod, "_clear_stop", _noop)
    monkeypatch.setattr(mod, "_check_stop", _noop)
    monkeypatch.setattr(mod, "_screenshot", lambda name="": "shot.png")
    monkeypatch.setattr(mod, "_screen_size", lambda: {"width": 100, "height": 100})
    monkeypatch.setattr(mod, "time", type("T", (), {"time": staticmethod(_time.time),
                                                    "sleep": staticmethod(_noop)}))

    replies = iter([
        {"success": True,
         "observation": '{"action":"move","x_ratio":0.5,"y_ratio":0.5,"reason":"测试"}'},
        {"success": True,
         "observation": '{"action":"quit","observation":"玩够了","reason":"结束"}'},
    ])
    applied = []
    states = []
    revoked = []
    monkeypatch.setattr(mod, "_look_prompt", lambda prompt, image: next(replies))
    monkeypatch.setattr(mod, "_apply_step", lambda step: applied.append(step))
    monkeypatch.setattr(mod, "_write_state", lambda **kw: states.append(kw))
    monkeypatch.setattr(mod, "_revoke_license", lambda: revoked.append(True))

    result = mod.execute({"action": "autopilot", "goal": "测试"})
    assert result["success"] is True
    assert result.get("quit") is True
    assert applied and applied[0]["action"] == "move"
    assert states[0]["active"] is True and states[0]["autopilot"] is True
    assert states[-1]["active"] is False and states[-1]["autopilot"] is False
    assert len(revoked) == 1


def test_autopilot_hints_cover_going_out():
    """“出门 / 看家”等说法要能触发授权判定，而不是被关键词表直接漏掉。"""
    sys.path.insert(0, os.path.join(ROOT, "src", "core"))
    import thinking_engine_api as tea

    hints = tea.ThinkingEngineAPIHandler._AUTOPILOT_TALK_HINTS
    for word in ("autopilot", "出门", "看家", "电脑给你"):
        assert word in hints
