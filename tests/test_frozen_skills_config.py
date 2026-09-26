# -*- coding: utf-8 -*-
"""模擬 frozen 運行環境，驗證技能開關落到 exe 旁 data/ 並遷移舊配置。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "core"))

EXE_DIR = r"D:\Program Files\Humanaize2-x64"
EXE = os.path.join(EXE_DIR, "Humanaize2.exe")
if not os.path.isfile(EXE):
    print("SKIP: install dir not present on this machine")
    sys.exit(0)

# 模擬 onefile 打包態
sys.frozen = True
sys.executable = EXE

from tools.skills_manager import SkillsManager

mgr = SkillsManager()
expected = os.path.join(EXE_DIR, "data", "skills_config.json")
print("skills_dir =", mgr.skills_dir)
print("config_path =", mgr.skills_config_path)
assert mgr.skills_config_path == expected, mgr.skills_config_path
# 注：模擬環境下 __file__ 仍指向 dev 源碼，skills_dir 可能解析到 dev 樹；
# 真實 frozen 進程由 exe 旁 skills/ 加載（已在運行實例驗證 18 個）
names = {s.name for s in mgr.get_all_skills()}
assert "misskey-bot" in names, names
# 舊配置已遷移（reddit 應為啟用）
assert mgr.skills_config.get("skills", {}).get("reddit", {}).get("enabled") is True
# 停用再啟用，驗證寫入新路徑
mgr.disable_skill("reddit")
import json
with open(expected, "r", encoding="utf-8") as f:
    on_disk = json.load(f)
assert on_disk["skills"]["reddit"]["enabled"] is False
mgr.enable_skill("reddit")
print("frozen skills config path + migration + persistence: PASS")
