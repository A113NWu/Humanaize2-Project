#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模式管理器模块
让AI可以根据情景需要启动Solve模式和Guard模式
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .color_logger import color_logger, ai_notifier
except ImportError:
    from .tools import SimpleLogger
    color_logger = SimpleLogger("mode_manager.log")
    ai_notifier = None


class ModeManager:
    """模式管理器"""
    
    def __init__(self):
        self.logger = color_logger
        self.active_modes = {}
        self.mode_threads = {}
        
        self.mode_config = {
            "solve": {
                "description": "问题解决模式，用于分析和解决复杂问题",
                "keywords": ["问题", "解决", "分析", "修复", "调试", "优化", "实现", "开发", "任务", "挑战",
                            "bug", "错误", "缺陷", "改进", "创建", "构建", "设计", "研究", "探索", "方案"],
                "min_confidence": 0.3
            },
            "guard": {
                "description": "安全守护模式，用于监控和防御网络攻击",
                "keywords": ["攻击", "安全", "威胁", "入侵", "防护", "防御", "防火墙", "检测", "恶意", "黑客",
                            "扫描", "渗透", "漏洞", "病毒", "木马", "钓鱼", "DDOS", "SQL注入", "XSS", "攻击检测"],
                "min_confidence": 0.3
            }
        }
    
    def analyze_context(self, context: str) -> Dict:
        """分析上下文，判断应该启动哪种模式"""
        context_lower = context.lower()
        results = {}
        
        for mode, config in self.mode_config.items():
            matched_keywords = []
            for keyword in config["keywords"]:
                if keyword in context_lower:
                    matched_keywords.append(keyword)
            
            if len(matched_keywords) >= 2:
                confidence = min(len(matched_keywords) / 5, 1.0)
            elif len(matched_keywords) == 1:
                confidence = 0.5
            else:
                confidence = 0.0
                
            results[mode] = {
                "matched_keywords": matched_keywords,
                "confidence": confidence,
                "should_activate": confidence >= config["min_confidence"],
                "description": config["description"]
            }
        
        return results
    
    def start_mode(self, mode: str, params: Optional[Dict] = None) -> Dict:
        """启动指定模式"""
        if mode not in self.mode_config:
            return {"status": "error", "message": f"Unknown mode: {mode}"}
        
        if mode in self.active_modes and self.active_modes[mode]["running"]:
            return {"status": "error", "message": f"{mode} mode is already running"}
        
        try:
            if mode == "solve":
                result = self._start_solve_mode(params)
            elif mode == "guard":
                result = self._start_guard_mode(params)
            else:
                return {"status": "error", "message": f"Unsupported mode: {mode}"}
            
            if result.get("status") == "success":
                self.active_modes[mode] = {
                    "running": True,
                    "started_at": datetime.now().isoformat(),
                    "params": params or {},
                    "thread": self.mode_threads.get(mode)
                }
                
                if ai_notifier:
                    ai_notifier.notify(
                        action_type="模式启动",
                        description=f"启动{mode}模式",
                        target="",
                        result="success",
                        details={"模式": mode, "参数": params or {}}
                    )
                
                self.logger.success(f"{mode}模式启动成功")
            
            return result
            
        except Exception as e:
            self.logger.error(f"启动{mode}模式失败: {e}")
            return {"status": "error", "message": f"Failed to start {mode} mode: {e}"}
    
    def _start_solve_mode(self, params: Optional[Dict] = None) -> Dict:
        """启动解决模式"""
        try:
            from .solve_mode import SolveMode
            
            problem = params.get("problem", "") if params else ""
            
            if not problem:
                return {"status": "error", "message": "Solve mode requires a problem parameter"}
            
            solver = SolveMode()
            
            if params:
                mode_args = []
                if params.get("hsn"):
                    mode_args.append("--hsn")
                if params.get("sandbox"):
                    mode_args.append("--sandbox")
                    mode_args.append(params["sandbox"])
                if params.get("gan"):
                    mode_args.append("-gan")
                solver.parse_args(mode_args)
            
            solver.set_problem(problem)
            
            def run_solve():
                try:
                    solver.run()
                except Exception as e:
                    self.logger.error(f"Solve mode error: {e}")
            
            thread = threading.Thread(target=run_solve, daemon=True)
            thread.start()
            self.mode_threads["solve"] = thread
            
            return {"status": "success", "message": "Solve mode started", "problem": problem}
            
        except ImportError as e:
            return {"status": "error", "message": f"Failed to import solve_mode: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Solve mode startup failed: {e}"}
    
    def _start_guard_mode(self, params: Optional[Dict] = None) -> Dict:
        """启动守护模式"""
        try:
            from .guard_mode import GuardMode
            
            background = params.get("background", False) if params else False
            start_on_boot = params.get("start_on_boot", False) if params else False
            
            guard = GuardMode(background=background, start_on_boot=start_on_boot)
            
            def run_guard():
                try:
                    guard.start()
                except Exception as e:
                    self.logger.error(f"Guard mode error: {e}")
            
            thread = threading.Thread(target=run_guard, daemon=True)
            thread.start()
            self.mode_threads["guard"] = thread
            
            return {
                "status": "success",
                "message": "Guard mode started",
                "background": background,
                "start_on_boot": start_on_boot
            }
            
        except ImportError as e:
            return {"status": "error", "message": f"Failed to import guard_mode: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Guard mode startup failed: {e}"}
    
    def stop_mode(self, mode: str) -> Dict:
        """停止指定模式"""
        if mode not in self.active_modes:
            return {"status": "error", "message": f"{mode} mode is not running"}
        
        try:
            if mode == "solve":
                from .solve_mode import SolveMode
                # SolveMode doesn't have a global instance, need to find another way
                pass
            elif mode == "guard":
                from .guard_mode import guard_mode_api
                result = guard_mode_api.stop()
                
                if ai_notifier:
                    ai_notifier.notify(
                        action_type="模式停止",
                        description=f"停止{mode}模式",
                        target="",
                        result="success"
                    )
                
                self.logger.success(f"{mode}模式已停止")
                return result
            
            self.active_modes[mode]["running"] = False
            
            return {"status": "success", "message": f"{mode} mode stopped"}
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to stop {mode} mode: {e}"}
    
    def get_mode_status(self, mode: str = None) -> Dict:
        """获取模式状态"""
        if mode:
            if mode in self.active_modes:
                return {"status": "success", "mode": mode, **self.active_modes[mode]}
            return {"status": "error", "message": f"{mode} mode not found"}
        
        return {
            "status": "success",
            "modes": {
                mode: {
                    "running": self.active_modes.get(mode, {}).get("running", False),
                    "started_at": self.active_modes.get(mode, {}).get("started_at"),
                    "description": self.mode_config[mode]["description"]
                }
                for mode in self.mode_config
            }
        }
    
    def suggest_mode(self, context: str) -> Dict:
        """根据上下文建议模式"""
        analysis = self.analyze_context(context)
        
        best_mode = None
        best_confidence = 0
        
        for mode, result in analysis.items():
            if result["confidence"] > best_confidence:
                best_confidence = result["confidence"]
                best_mode = mode
        
        if best_mode and best_confidence >= self.mode_config[best_mode]["min_confidence"]:
            return {
                "status": "success",
                "suggested_mode": best_mode,
                "confidence": best_confidence,
                "analysis": analysis,
                "action": f"建议启动{best_mode}模式"
            }
        
        return {
            "status": "success",
            "suggested_mode": None,
            "confidence": 0,
            "analysis": analysis,
            "action": "无需启动特殊模式"
        }


class ModeManagerAPI:
    """模式管理器API"""
    
    def __init__(self):
        self.manager = ModeManager()
    
    def analyze_context(self, context: str) -> Dict:
        """分析上下文"""
        return {"status": "success", "data": self.manager.analyze_context(context)}
    
    def suggest_mode(self, context: str) -> Dict:
        """建议模式"""
        return self.manager.suggest_mode(context)
    
    def start_mode(self, mode: str, params: Optional[Dict] = None) -> Dict:
        """启动模式"""
        return self.manager.start_mode(mode, params)
    
    def stop_mode(self, mode: str) -> Dict:
        """停止模式"""
        return self.manager.stop_mode(mode)
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {"status": "success", "data": self.manager.get_mode_status()}


mode_manager = ModeManagerAPI()