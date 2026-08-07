#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Storage Manager - 系統存儲空間管理與清理優化

功能:
- 監控磁盤空間使用情況
- 清理臨時文件、緩存、日誌
- 自動維護存儲空間
- 生成臨時文件（自動清理）
"""

import os
import sys
import shutil
import tempfile
import time
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageManager:
    """系統存儲空間管理器"""

    # 默認臨時文件生命週期（秒）
    DEFAULT_TTL = 3600  # 1 小時
    # 低磁盤空間閾值（百分比）
    LOW_SPACE_THRESHOLD = 90

    def __init__(self, project_root: str = None):
        self._project_root = project_root or os.getcwd()
        self._temp_dir = os.path.join(self._project_root, "temp")
        self._cache_dir = os.path.join(self._project_root, "cache")
        self._logs_dir = os.path.join(self._project_root, "logs")
        self._build_dir = os.path.join(self._project_root, "build")
        self._dist_dir = os.path.join(self._project_root, "dist")
        self._installer_output_dir = os.path.join(self._project_root, "installer_output")
        self._tracked_temp_files: List[Dict] = []
        self._ensure_dirs()

    def _ensure_dirs(self):
        """確保所有必要目錄存在"""
        for dir_path in [self._temp_dir, self._cache_dir, self._logs_dir]:
            os.makedirs(dir_path, exist_ok=True)

    # ==================== 磁盤空間監控 ====================

    def get_disk_usage(self) -> Dict:
        """獲取當前磁盤使用情況"""
        try:
            usage = shutil.disk_usage(self._project_root)
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": round(usage.used / usage.total * 100, 1),
                "is_low_space": usage.used / usage.total * 100 >= self.LOW_SPACE_THRESHOLD,
            }
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return {"error": str(e)}

    def get_project_size(self) -> Dict:
        """獲取項目各目錄大小"""
        sizes = {}
        dirs_to_check = {
            "temp": self._temp_dir,
            "cache": self._cache_dir,
            "logs": self._logs_dir,
            "build": self._build_dir,
            "dist": self._dist_dir,
            "installer_output": self._installer_output_dir,
        }
        for name, path in dirs_to_check.items():
            if os.path.exists(path):
                try:
                    total_size = 0
                    file_count = 0
                    for dirpath, dirnames, filenames in os.walk(path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            try:
                                total_size += os.path.getsize(fp)
                                file_count += 1
                            except OSError:
                                pass
                    sizes[name] = {
                        "size_mb": round(total_size / (1024**2), 2),
                        "size_bytes": total_size,
                        "file_count": file_count,
                    }
                except Exception as e:
                    sizes[name] = {"error": str(e)}
            else:
                sizes[name] = {"size_mb": 0, "size_bytes": 0, "file_count": 0}

        total = sum(s.get("size_bytes", 0) for s in sizes.values())
        sizes["_total"] = {
            "size_mb": round(total / (1024**2), 2),
            "size_bytes": total,
        }
        return sizes

    # ==================== 臨時文件管理 ====================

    def create_temp_file(self, suffix: str = "", prefix: str = "", content: str = None, ttl: int = None) -> str:
        """創建臨時文件並返回路徑

        Args:
            suffix: 文件後綴
            prefix: 文件前綴
            content: 初始內容
            ttl: 生存時間（秒），None 表示使用默認值

        Returns:
            臨時文件路徑
        """
        fd, path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=self._temp_dir,
        )
        if content:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            os.close(fd)

        self._tracked_temp_files.append({
            "path": path,
            "created_at": time.time(),
            "ttl": ttl or self.DEFAULT_TTL,
        })
        return path

    def create_temp_dir(self, suffix: str = "", prefix: str = "") -> str:
        """創建臨時目錄並返回路徑"""
        path = tempfile.mkdtemp(
            suffix=suffix,
            prefix=prefix,
            dir=self._temp_dir,
        )
        self._tracked_temp_files.append({
            "path": path,
            "created_at": time.time(),
            "ttl": self.DEFAULT_TTL,
            "is_dir": True,
        })
        return path

    def cleanup_expired_temp_files(self) -> Dict:
        """清理過期的臨時文件"""
        removed = 0
        freed_bytes = 0
        now = time.time()

        for entry in self._tracked_temp_files[:]:
            if now - entry["created_at"] >= entry["ttl"]:
                path = entry["path"]
                is_dir = entry.get("is_dir", False)
                try:
                    if is_dir:
                        if os.path.exists(path):
                            dir_size = self._get_dir_size(path)
                            shutil.rmtree(path, ignore_errors=True)
                            freed_bytes += dir_size
                            removed += 1
                        self._tracked_temp_files.remove(entry)
                    else:
                        if os.path.exists(path):
                            file_size = os.path.getsize(path)
                            os.unlink(path)
                            freed_bytes += file_size
                            removed += 1
                        self._tracked_temp_files.remove(entry)
                except Exception as e:
                    logger.warning(f"Failed to clean temp file {path}: {e}")

        return {
            "removed_count": removed,
            "freed_mb": round(freed_bytes / (1024**2), 2),
            "freed_bytes": freed_bytes,
        }

    # ==================== 全面清理 ====================

    def cleanup_all(self, aggressive: bool = False) -> Dict:
        """執行全面清理

        Args:
            aggressive: 是否執行積極清理（包含 build 和 dist 目錄）
        """
        results = {
            "temp": self._cleanup_dir(self._temp_dir),
            "cache": self._cleanup_dir(self._cache_dir),
            "logs": self._cleanup_logs(),
        }

        if aggressive:
            results["build"] = self._cleanup_dir(self._build_dir)
            results["dist"] = self._cleanup_dir(self._dist_dir)

        results["expired_temp"] = self.cleanup_expired_temp_files()
        results["freed_total_mb"] = round(
            sum(r.get("freed_bytes", 0) for r in results.values()) / (1024**2), 2
        )

        return results

    def _cleanup_dir(self, dir_path: str) -> Dict:
        """清理指定目錄"""
        if not os.path.exists(dir_path):
            return {"freed_bytes": 0, "files_removed": 0}

        freed_bytes = 0
        files_removed = 0
        try:
            dir_size = self._get_dir_size(dir_path)
            shutil.rmtree(dir_path, ignore_errors=True)
            os.makedirs(dir_path, exist_ok=True)
            freed_bytes = dir_size
        except Exception as e:
            logger.error(f"Failed to cleanup {dir_path}: {e}")

        return {
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024**2), 2),
            "files_removed": files_removed,
        }

    def _cleanup_logs(self) -> Dict:
        """清理日誌文件（保留最近 7 天）"""
        if not os.path.exists(self._logs_dir):
            return {"freed_bytes": 0, "files_removed": 0}

        freed_bytes = 0
        files_removed = 0
        cutoff_time = time.time() - (7 * 86400)

        for dirpath, dirnames, filenames in os.walk(self._logs_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    if mtime < cutoff_time:
                        file_size = os.path.getsize(filepath)
                        os.unlink(filepath)
                        freed_bytes += file_size
                        files_removed += 1
                except OSError:
                    pass

        return {
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024**2), 2),
            "files_removed": files_removed,
        }

    def _get_dir_size(self, dir_path: str) -> int:
        """獲取目錄總大小"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception:
            pass
        return total

    # ==================== 低磁盤空間自動清理 ====================

    def auto_cleanup_if_needed(self, threshold_percent: float = None) -> Dict:
        """如果磁盤空間不足則自動清理

        Args:
            threshold_percent: 使用百分比閾值，超過則觸發清理
        """
        threshold = threshold_percent or self.LOW_SPACE_THRESHOLD
        disk = self.get_disk_usage()

        if disk.get("percent_used", 0) >= threshold:
            logger.info(f"Low disk space detected ({disk['percent_used']}%), triggering cleanup")
            return self.cleanup_all(aggressive=False)

        return {"status": "ok", "disk_usage": disk}

    # ==================== 臨時文件標籤/分類 ====================

    def get_cleanup_report(self) -> str:
        """生成清理報告"""
        disk = self.get_disk_usage()
        project_sizes = self.get_project_size()

        lines = [
            "=== 存儲空間報告 ===",
            f"磁盤總計: {disk.get('total_gb', 'N/A')} GB",
            f"已使用: {disk.get('used_gb', 'N/A')} GB ({disk.get('percent_used', 'N/A')}%)",
            f"可用: {disk.get('free_gb', 'N/A')} GB",
            "",
            "--- 項目目錄大小 ---",
        ]

        for name, info in project_sizes.items():
            if name.startswith("_"):
                continue
            if isinstance(info, dict) and "size_mb" in info:
                lines.append(f"  {name}: {info['size_mb']} MB ({info['file_count']} files)")

        total = project_sizes.get("_total", {})
        if total:
            lines.append(f"  項目總計: {total.get('size_mb', 0)} MB")

        if disk.get("is_low_space"):
            lines.append("")
            lines.append("⚠ 磁盤空間不足！建議執行清理。")

        return "\n".join(lines)


# 全局 StorageManager 實例
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """獲取全局 StorageManager 實例"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
