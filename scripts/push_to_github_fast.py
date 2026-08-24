#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速版：只对比新增/修改过的几个关键文件，而不是扫描整个工作区（astrbot skills 目录太大）。
扫描策略：
  1) 遍历仓库，跳过 skills/qq-chat/astrbot（这子项目保持原样即可，先做 exclude 实验）
  2) 仅针对本次变更过的路径做 blob 上传
  3) 删除 / 添加 / 替换均显式列出
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GITHUB_API = "https://api.github.com"
API_VERSION_HEADER = "2022-11-28"


def _read_reg_env(name: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore
    except Exception:
        return None
    for hive, sub in [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ]:
        try:
            with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ) as k:
                v, _ = winreg.QueryValueEx(k, name)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        except OSError:
            continue
    return None


# ========== 本次变更路径（精确） ==========
CHANGED_FILES = [
    "installer/windows/build_exe.py",
    "installer/windows/humanaize2-x86_64.iss",
    "installer/windows/humanaize2.iss",
    "installer/windows/humanaize2-arm64.iss",
    "config/version.json",
    "src/core/voice/voice_service.py",
    "src/core/voice/tts_synthesizer.py",
    "src/core/ui/ui.py",
]
# 允许若不存在则跳过（避免误删）


def read_gitignore():
    gi = PROJECT_ROOT / ".gitignore"
    pats = set()
    if gi.exists():
        for raw in gi.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            pats.add(line.rstrip("/"))
    return list(pats)


EXCLUDED_DIR_NAMES = {
    ".git", "build_env", "__pycache__", "node_modules", ".gradle", ".idea", ".vscode",
    "build", "dist", "installer_output", "venv", ".venv", ".mypy_cache",
    "apt-repo", "captures", ".externalNativeBuild", ".cxx", "android_client/app/build",
}
EXCLUDED_FILE_NAMES = {
    "Humanaize2.spec", ".DS_Store", "Thumbs.db", "desktop.ini", "local.properties",
    "build_log_x86_64.txt", "build_log_x86_64_continue.txt", "test_solve_reference.py",
}
EXCLUDED_FILE_GLOBS = [
    "*.exe", "*.apk", "*.aab", "*.bin", "*.gguf", "*.db*", "*.log",
    "build_log_*.txt", "*-portable.zip", "*.zip", "*.tar.gz",
    "*.deb", "*.rpm", "*.AppImage", "*.pyc", "*.pyo", "*.pyd",
]


def ignored_by_gitignore(rel: str, name: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if pat.startswith("/"):
            pat = pat[1:]
        if "*" in pat:
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
                return True
        else:
            if name == pat or rel == pat or rel.startswith(pat + "/"):
                return True
    return False


def collect_files_fast(limit_paths: Optional[List[str]] = None) -> Dict[str, bytes]:
    ignore_patterns = read_gitignore()
    result: Dict[str, bytes] = {}

    if limit_paths:
        # 精确模式
        for rel in limit_paths:
            abs_path = PROJECT_ROOT / rel
            if not abs_path.exists() or not abs_path.is_file():
                print(f"   [SKIP] changed file missing: {rel}")
                continue
            if ignored_by_gitignore(rel, abs_path.name, ignore_patterns):
                # 版本文件不应该被忽略，但确认一下
                print(f"   [WARN] changed file would be ignored by .gitignore? {rel}")
            size = abs_path.stat().st_size
            if size > 100 * 1024 * 1024:
                print(f"   [SKIP] too large: {rel}")
                continue
            try:
                result[rel] = abs_path.read_bytes()
                print(f"   [ADD] {rel} ({size} bytes)")
            except OSError as e:
                print(f"   [SKIP] read fail: {rel}: {e}")
        return result

    # 全量扫描（未使用）
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        pruned = []
        for d in list(dirnames):
            if d in EXCLUDED_DIR_NAMES:
                continue
            abs_dir = Path(dirpath) / d
            rel = abs_dir.relative_to(PROJECT_ROOT).as_posix()
            if rel and ignored_by_gitignore(rel, d, ignore_patterns):
                continue
            pruned.append(d)
        dirnames[:] = pruned

        for fn in filenames:
            abs_file = Path(dirpath) / fn
            rel = abs_file.relative_to(PROJECT_ROOT).as_posix()
            if fn in EXCLUDED_FILE_NAMES:
                continue
            if any(fnmatch.fnmatch(fn, g) for g in EXCLUDED_FILE_GLOBS):
                continue
            if ignored_by_gitignore(rel, fn, ignore_patterns):
                continue
            size = abs_file.stat().st_size
            if size > 100 * 1024 * 1024:
                continue
            try:
                result[rel] = abs_file.read_bytes()
            except OSError:
                pass
    return result


def gh_request(method, path, token, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION_HEADER,
        "User-Agent": "Humanaize2-Deploy",
    }
    headers.update(kwargs.pop("headers", {}))
    r = requests.request(method, GITHUB_API + path, headers=headers, timeout=90, **kwargs)
    if r.status_code >= 400:
        print(f"[HTTP ERR {r.status_code}] {method} {path}: {r.text[:800]}")
        raise SystemExit(3)
    return r


def blob_sha(content: bytes) -> str:
    h = hashlib.sha1()
    h.update(f"blob {len(content)}\x00".encode("utf-8"))
    h.update(content)
    return h.hexdigest()


def upload_blob(token, repo, content) -> str:
    r = gh_request("POST", f"/repos/{repo}/git/blobs", token,
                   json={"content": base64.b64encode(content).decode("ascii"),
                         "encoding": "base64"})
    return r.json()["sha"]


def get_remote_tree(token, repo, tree_sha) -> Dict[str, Tuple[str, str]]:
    """{path: (type, sha)}"""
    r = gh_request("GET", f"/repos/{repo}/git/trees/{tree_sha}?recursive=1", token)
    d = r.json()
    result: Dict[str, Tuple[str, str]] = {}
    for e in d.get("tree", []):
        result[e["path"]] = (e["type"], e.get("sha", ""))
    # 可能被截断，但我们只改几个文件不影响
    return result


def main():
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
             or _read_reg_env("GITHUB_TOKEN") or _read_reg_env("GH_TOKEN"))
    if not token:
        print("ERROR: need GITHUB_TOKEN")
        return 2

    repo = os.getenv("GITHUB_REPO", "A113NWu/Humanaize2-Project")
    branch = "main"
    commit_msg = "chore(release): v2.2.6 - TTS voice cloning + installer uac-admin fixed"

    print(f"[1/5] Collect changed files ({len(CHANGED_FILES)} targeted)...")
    local = collect_files_fast(CHANGED_FILES)
    print(f"      Collected {len(local)} files")

    print(f"[2/5] Remote HEAD of {repo} refs/heads/{branch}...")
    head = gh_request("GET", f"/repos/{repo}/git/ref/heads/{branch}", token).json()
    head_commit_sha = head["object"]["sha"]
    print(f"      HEAD commit: {head_commit_sha}")

    commit_obj = gh_request("GET", f"/repos/{repo}/git/commits/{head_commit_sha}", token).json()
    base_tree_sha = commit_obj["tree"]["sha"]
    parents = [head_commit_sha]  # [p["sha"] for p in commit_obj.get("parents", [])] or [head_commit_sha]

    print(f"[3/5] Fetch remote tree...")
    remote = get_remote_tree(token, repo, base_tree_sha)
    print(f"      Remote entries: {len(remote)}")

    print(f"[4/5] Build tree entries...")
    entries: List[dict] = []
    up = reup = 0
    for rel, content in local.items():
        expected = blob_sha(content)
        _, remote_sha = remote.get(rel, ("", ""))
        if remote_sha == expected:
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": remote_sha})
            reup += 1
        else:
            s = upload_blob(token, repo, content)
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": s})
            up += 1
            print(f"      uploaded [{up}] {rel} -> {s[:10]}...")
    print(f"      -> uploaded={up} new blobs, reused={reup}")

    print(f"[5/5] Create new tree + commit + update ref...")
    new_tree = gh_request("POST", f"/repos/{repo}/git/trees", token,
                          json={"base_tree": base_tree_sha, "tree": entries}).json()["sha"]
    print(f"      new tree: {new_tree}")

    # 提交作者信息
    try:
        user_info = gh_request("GET", "/user", token).json()
        author_name = user_info.get("name") or user_info.get("login") or "Allen Wu"
        author_email = f"{user_info.get('id')}+{user_info.get('login')}@users.noreply.github.com"
    except Exception:
        author_name = "Allen Wu"
        author_email = "allenwu@users.noreply.github.com"

    new_commit = gh_request("POST", f"/repos/{repo}/git/commits", token, json={
        "message": commit_msg,
        "tree": new_tree,
        "parents": parents,
        "author": {"name": author_name, "email": author_email},
    }).json()["sha"]
    print(f"      new commit: {new_commit}")

    gh_request("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", token,
               json={"sha": new_commit, "force": False})

    print("✅ 推送成功")
    print(f"   commit URL: https://github.com/{repo}/commit/{new_commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
