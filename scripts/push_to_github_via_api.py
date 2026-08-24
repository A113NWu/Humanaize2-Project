#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 GitHub REST API（Git Database）提交代码。
仅用于 github.com 被墙但 api.github.com 可直接访问的场景。
用法：
    set GITHUB_TOKEN=ghp_xxx
    python scripts/push_to_github_via_api.py [--repo A113NWu/Humanaize2-Project] [--branch main]

变更依据：工作区 vs 远端分支最新树，执行等价于 git add -A && git commit && git push
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import os
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


def _read_reg_env(name: str) -> Optional[str]:
    """从 Windows 注册表 User/Machine 域读取环境变量，规避 shell 不继承问题"""
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
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 60
API_VERSION_HEADER = "2022-11-28"


def read_gitignore_patterns(root: Path) -> List[Path]:
    """
    返回一组应排除的绝对路径（按规则展开）。
    简单实现：解析根级 .gitignore，不处理嵌套。
    """
    ignore_set = set()
    gi = root / ".gitignore"
    if not gi.exists():
        return []
    for raw in gi.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.rstrip("/")
        if line.startswith("/"):
            line = line[1:]
        # 简单通配：支持 * 和 末尾/ 目录
        ignore_set.add(line)
    return list(ignore_set)


def should_skip(rel_posix: str, abs_path: Path, ignore_patterns: List[str],
                default_excludes: Tuple[str, ...]) -> bool:
    # 默认排除（二进制产物、Git 元数据、虚拟环境等）
    for part in rel_posix.split("/"):
        if part in default_excludes:
            return True
    if rel_posix in default_excludes:
        return True

    # 来自 .gitignore
    name = abs_path.name
    for pat in ignore_patterns:
        if "*" in pat:
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel_posix, pat):
                return True
        else:
            if name == pat or rel_posix == pat or rel_posix.startswith(pat + "/"):
                return True
    return False


DEFAULT_EXCLUDES = (
    ".git", ".github",  # .github 保留，不排除；这里显式说明，后面再调
    "build_env", "__pycache__", "node_modules", ".gradle", ".idea", ".vscode",
    "build", "dist", "installer_output", "apt-repo",
    "venv", ".venv", "build_log_x86_64.txt", "build_log_x86_64_continue.txt",
    "Humanaize2.spec", "test_solve_reference.py", "scripts",
)

# 保留（提交）.github workflows
KEEP = {".github"}


def collect_workspace_files(root: Path, ignore_patterns: List[str]) -> Dict[str, bytes]:
    """返回 {相对路径(posix): 二进制内容}"""
    result: Dict[str, bytes] = {}
    default_excludes = tuple(x for x in DEFAULT_EXCLUDES if x not in KEEP)
    for dirpath, dirnames, filenames in os.walk(root):
        # 对 dirnames 原地过滤，避免下钻
        pruned = []
        for d in list(dirnames):
            abs_dir = Path(dirpath) / d
            rel_dir = abs_dir.relative_to(root).as_posix()
            if should_skip(rel_dir, abs_dir, ignore_patterns, default_excludes):
                continue
            pruned.append(d)
        dirnames[:] = pruned

        for fn in filenames:
            abs_file = Path(dirpath) / fn
            rel = abs_file.relative_to(root).as_posix()
            if should_skip(rel, abs_file, ignore_patterns, default_excludes):
                continue
            # 100 MB 上限的文件（GitHub API blob 创建同样限制 100MB）
            try:
                size = abs_file.stat().st_size
            except OSError:
                continue
            if size > 100 * 1024 * 1024:
                print(f"[SKIP] 超大文件 (>100MB): {rel}")
                continue
            try:
                result[rel] = abs_file.read_bytes()
            except OSError as exc:
                print(f"[SKIP] 读取失败 {rel}: {exc}")
    return result


def gh_request(method: str, path: str, token: str, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION_HEADER,
        "User-Agent": "Humanaize2-Deploy",
    }
    headers.update(kwargs.pop("headers", {}))
    url = GITHUB_API + path
    resp = requests.request(method, url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)
    if resp.status_code >= 400:
        print(f"[HTTP ERR] {method} {path} -> {resp.status_code}: {resp.text[:600]}")
        raise SystemExit(2)
    return resp


def get_ref(token: str, repo: str, branch: str) -> str:
    resp = gh_request("GET", f"/repos/{repo}/git/ref/heads/{branch}", token)
    data = resp.json()
    return data["object"]["sha"]


def get_commit(token: str, repo: str, sha: str) -> Tuple[str, str]:
    resp = gh_request("GET", f"/repos/{repo}/git/commits/{sha}", token)
    d = resp.json()
    return d["tree"]["sha"], d["author"], d.get("parents", [{"sha": p["sha"]} for p in d.get("parents", [])])


def fetch_tree_entries(token: str, repo: str, tree_sha: str, prefix: str = "") -> Dict[str, Tuple[str, str]]:
    """
    递归拉取完整 remote tree，返回 {rel_posix: (type, sha)}。
    用于对比本地文件以决定是否需要新建 blob。
    """
    result: Dict[str, Tuple[str, str]] = {}
    resp = gh_request("GET", f"/repos/{repo}/git/trees/{tree_sha}?recursive=1", token)
    d = resp.json()
    for entry in d.get("tree", []):
        path = entry["path"]
        full = prefix + path
        result[full] = (entry["type"], entry.get("sha", ""))
    if d.get("truncated"):
        print("[WARN] 远端 tree 被截断，大仓库可能导致树差异比较不准")
    return result


def blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\x00".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def upload_blob(token: str, repo: str, content: bytes) -> str:
    b64 = base64.b64encode(content).decode("ascii")
    resp = gh_request("POST", f"/repos/{repo}/git/blobs", token,
                      json={"content": b64, "encoding": "base64"})
    return resp.json()["sha"]


def create_tree(token: str, repo: str, entries: List[dict], base_tree: Optional[str]) -> str:
    payload = {"tree": entries}
    if base_tree:
        payload["base_tree"] = base_tree
    resp = gh_request("POST", f"/repos/{repo}/git/trees", token, json=payload)
    return resp.json()["sha"]


def create_commit(token: str, repo: str, message: str, tree_sha: str,
                  parent_shas: List[str]) -> str:
    author = {"name": "Allen Wu", "email": "allenwu@users.noreply.github.com"}
    resp = gh_request("POST", f"/repos/{repo}/git/commits", token,
                      json={"message": message, "tree": tree_sha,
                            "parents": parent_shas, "author": author})
    return resp.json()["sha"]


def update_ref(token: str, repo: str, branch: str, new_sha: str, force: bool = False):
    gh_request("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", token,
               json={"sha": new_sha, "force": force})


def build_path_trees(desired_entries: List[dict]) -> List[dict]:
    """
    desired_entries: 完整路径条目 [{path, mode, type, sha}]
    返回：按目录层级的 entries，用于 create_tree（只在根上建树）。
    为简单起见，直接把完整平坦列表传 create_tree，GitHub 端会自动建立目录结构。
    """
    return desired_entries


def main():
    parser = argparse.ArgumentParser(description="Push workspace to GitHub via REST API")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPO", "A113NWu/Humanaize2-Project"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", default=f"chore(release): bump to v2.2.6 + TTS synthesizer + uac-admin fix")
    args = parser.parse_args()

    # 尝试从多个位置读取 token（子进程 shell 往往不继承 USER 环境变量）
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
             or _read_reg_env("GITHUB_TOKEN") or _read_reg_env("GH_TOKEN"))
    if not token:
        print("ERROR: GITHUB_TOKEN env var is not set (process, User or Machine)")
        return 2

    print(f"[1/6] 收集本地工作区文件...")
    ignore_patterns = read_gitignore_patterns(PROJECT_ROOT)
    local_files = collect_workspace_files(PROJECT_ROOT, ignore_patterns)
    print(f"      共 {len(local_files)} 个文件将被纳入 tree 对比")

    print(f"[2/6] 获取远端 {args.repo} refs/heads/{args.branch} ...")
    head_sha = get_ref(token, args.repo, args.branch)
    print(f"      head commit: {head_sha}")

    resp = gh_request("GET", f"/repos/{args.repo}/git/commits/{head_sha}", token)
    commit_obj = resp.json()
    root_tree_sha = commit_obj["tree"]["sha"]
    parent_shas = [p["sha"] for p in commit_obj.get("parents", [])] or [head_sha]

    print(f"[3/6] 拉取远端 tree 做 SHA 对比...")
    remote_tree = fetch_tree_entries(token, args.repo, root_tree_sha)
    print(f"      远端文件条目: {len(remote_tree)}")

    # 计算本地哪些需要新 blob，删除远端多余条目
    local_paths = set(local_files.keys())
    remote_paths = {p for p, (t, _) in remote_tree.items() if t == "blob"}

    to_delete = remote_paths - local_paths
    print(f"      需要删除文件: {len(to_delete)}, 新增/更新文件: {len(local_paths)}")

    # 上传所有新增/变更 blob
    print(f"[4/6] 上传变更 blobs (SHA 比对)...")
    desired_entries: List[dict] = []
    uploaded = 0
    skipped = 0
    progress_mod = max(1, len(local_files) // 40)
    for idx, (rel, content) in enumerate(local_files.items()):
        expected = blob_sha(content)
        _, remote_sha = remote_tree.get(rel, ("", ""))
        if remote_sha == expected:
            # 文件未变 -> 沿用现有条目信息
            desired_entries.append({"path": rel, "mode": "100644",
                                    "type": "blob", "sha": remote_sha})
            skipped += 1
        else:
            sha = upload_blob(token, args.repo, content)
            desired_entries.append({"path": rel, "mode": "100644",
                                    "type": "blob", "sha": sha})
            uploaded += 1
        if idx % progress_mod == 0:
            print(f"      progress {idx}/{len(local_files)} (uploaded={uploaded}, unchanged={skipped})")
    print(f"      -> uploaded {uploaded} new blobs, reused {skipped} existing")

    # 对于待删除文件，不在 desired 中出现即可；GitHub create_tree(base_tree=X) 会把 base_tree 中
    # 没出现的路径保留，所以必须用显式 null 条目来删除。
    if to_delete:
        print(f"[4b/6] 标记 {len(to_delete)} 个文件删除...")
        for p in to_delete:
            desired_entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})

    print(f"[5/6] 创建新 tree + commit ...")
    new_tree_sha = create_tree(token, args.repo, build_path_trees(desired_entries), root_tree_sha)
    print(f"      new tree: {new_tree_sha}")
    new_commit_sha = create_commit(token, args.repo, args.message, new_tree_sha, parent_shas)
    print(f"      new commit: {new_commit_sha}")

    print(f"[6/6] 更新 refs/heads/{args.branch} -> {new_commit_sha} ...")
    update_ref(token, args.repo, args.branch, new_commit_sha, force=False)

    print("✅ 推送完成")
    print(f"   https://github.com/{args.repo}/commit/{new_commit_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
