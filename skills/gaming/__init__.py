# -*- coding: utf-8 -*-
"""
Humanaize Gaming Skill - AI游戏技能

功能：
1. 屏幕捕获 - 获取游戏画面
2. 键鼠控制 - 控制游戏角色（支持游戏配置文件）
3. 游戏状态检测 - 多层死亡检测（文字/OCR、血条监控、画面突变、LLM视觉判断）
4. 记忆路由 - 失败记录到经验模块，正常记录到记忆模块
5. GAN禁用 - 游戏时自动关闭GAN节省算力
6. 紧急停止 - 快捷键强制终止
7. 游戏配置文件 - 支持不同游戏的自定义操作映射和死亡检测策略
"""

import os
import sys
import json
import base64
import threading
import time
from typing import Dict, Any, Optional, List

_PYAUTOGUI_MODULE = None
_CV2_MODULE = None
_NUMPY_MODULE = None
_PIL_MODULE = None
_TESSERACT_MODULE = None
_KEYBOARD_MODULE = None

def _lazy_import_pyautogui():
    global _PYAUTOGUI_MODULE
    if _PYAUTOGUI_MODULE is None:
        try:
            import pyautogui
            _PYAUTOGUI_MODULE = pyautogui
        except ImportError:
            pass
    return _PYAUTOGUI_MODULE

def _lazy_import_cv2():
    global _CV2_MODULE
    if _CV2_MODULE is None:
        try:
            import cv2
            _CV2_MODULE = cv2
        except ImportError:
            pass
    return _CV2_MODULE

def _lazy_import_numpy():
    global _NUMPY_MODULE
    if _NUMPY_MODULE is None:
        try:
            import numpy as np
            _NUMPY_MODULE = np
        except ImportError:
            pass
    return _NUMPY_MODULE

def _lazy_import_pil():
    global _PIL_MODULE
    if _PIL_MODULE is None:
        try:
            from PIL import Image, ImageGrab
            _PIL_MODULE = (Image, ImageGrab)
        except ImportError:
            pass
    return _PIL_MODULE

def _lazy_import_tesseract():
    global _TESSERACT_MODULE
    if _TESSERACT_MODULE is None:
        try:
            import pytesseract
            _TESSERACT_MODULE = pytesseract
        except ImportError:
            pass
    return _TESSERACT_MODULE

def _lazy_import_keyboard():
    global _KEYBOARD_MODULE
    if _KEYBOARD_MODULE is None:
        try:
            import keyboard
            _KEYBOARD_MODULE = keyboard
        except ImportError:
            pass
    return _KEYBOARD_MODULE


class GamingSkill:
    """游戏技能核心类"""
    
    def __init__(self):
        self.game_running = False
        self.game_loop_thread = None
        self.fps = 5
        self.screenshot_interval = 1.0 / self.fps
        self.last_screenshot_time = 0
        self.current_frame = None
        self.frame_count = 0
        self.game_state = "playing"
        self.death_count = 0
        self.last_death_time = 0
        self.death_cooldown = 5
        self.emergency_stop_triggered = False
        
        self._current_profile = None
        self._profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
        
        self._reference_frame = None
        self._reference_frame_time = 0
        self._reference_frame_interval = 3.0
        
        self._health_bar_reference_color = None
        self._health_bar_reference_time = 0
        
        self._time_limit_start = 0
        self._time_limit_remaining = 0
        self._time_limit_last_check = 0
        
        self._setup_emergency_stop()
        self.load_profile("generic")
    
    def _setup_emergency_stop(self):
        """设置紧急停止快捷键监听"""
        keyboard = _lazy_import_keyboard()
        if not keyboard:
            return
        try:
            keyboard.add_hotkey('ctrl+shift+q', self._emergency_stop)
            keyboard.add_hotkey('esc', self._emergency_stop)
        except Exception:
            pass
    
    def _emergency_stop(self):
        """紧急停止 - 立即终止所有游戏操作"""
        if self.game_running:
            self.emergency_stop_triggered = True
            self.game_running = False
            self.game_state = "stopped"
            print("[Gaming Skill] 紧急停止已触发！")
    
    def _cleanup_emergency_stop(self):
        """清理快捷键监听"""
        keyboard = _lazy_import_keyboard()
        if not keyboard:
            return
        try:
            keyboard.remove_hotkey('ctrl+shift+q')
            keyboard.remove_hotkey('esc')
        except Exception:
            pass
    
    def get_profiles(self) -> List[str]:
        """获取可用的游戏配置文件列表"""
        profiles = []
        try:
            if os.path.exists(self._profiles_dir):
                for filename in os.listdir(self._profiles_dir):
                    if filename.endswith(".json") and filename != "schema.json":
                        profiles.append(filename[:-5])
        except Exception:
            pass
        return profiles
    
    def load_profile(self, profile_name: str) -> Dict:
        """加载游戏配置文件"""
        profile_path = os.path.join(self._profiles_dir, f"{profile_name}.json")
        
        if not os.path.exists(profile_path):
            return {
                "success": False,
                "error": f"配置文件不存在: {profile_name}.json",
                "available_profiles": self.get_profiles()
            }
        
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                self._current_profile = json.load(f)
            
            self._reset_death_detection_state()
            
            return {
                "success": True,
                "game_name": self._current_profile.get("game_name", "Unknown"),
                "description": self._current_profile.get("description", ""),
                "controls_count": len(self._current_profile.get("controls", [])),
                "death_detection_methods": self._current_profile.get("death_detection", {}).get("enabled_methods", [])
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"加载配置文件失败: {str(e)}"
            }
    
    def _reset_death_detection_state(self):
        """重置死亡检测状态"""
        self._reference_frame = None
        self._reference_frame_time = 0
        self._health_bar_reference_color = None
        self._health_bar_reference_time = 0
        
    def _reset_time_limit_state(self):
        """重置时间限制状态"""
        self._time_limit_start = time.time()
        self._time_limit_remaining = 0
        self._time_limit_last_check = 0
    
    def get_current_profile(self) -> Dict:
        """获取当前游戏配置"""
        return self._current_profile or {}
    
    def _get_death_keywords(self) -> List[str]:
        """获取当前配置的死亡关键词"""
        if self._current_profile:
            death_detection = self._current_profile.get("death_detection", {})
            text_config = death_detection.get("text", {})
            keywords = text_config.get("keywords", [])
            if keywords:
                return keywords
            
            return self._current_profile.get("death_keywords", [])
        
        return [
            "game over", "gameover", "you died", "you are dead",
            "你死了", "失败", "死亡", "挑战失败", "关卡失败",
            "game over!", "you died!", "dead", "defeat",
            "continue?", "restart", "重试", "重新开始"
        ]
    
    def _get_death_detection_config(self) -> Dict:
        """获取死亡检测配置"""
        if self._current_profile:
            return self._current_profile.get("death_detection", {})
        return {}
    
    def _get_all_keys(self) -> List[str]:
        """获取当前配置中的所有按键"""
        keys = []
        if self._current_profile:
            for control in self._current_profile.get("controls", []):
                if control.get("type") == "key" and control.get("keys"):
                    keys.extend(control.get("keys", []))
        return list(set(keys))
    
    def _get_control_by_action(self, action: str) -> Optional[Dict]:
        """根据操作名获取控制配置"""
        if self._current_profile:
            for control in self._current_profile.get("controls", []):
                if control.get("action") == action:
                    return control
        return None
    
    def capture_screen(self) -> Dict:
        """捕获屏幕截图"""
        pil_import = _lazy_import_pil()
        np = _lazy_import_numpy()
        cv2 = _lazy_import_cv2()
        
        if not pil_import:
            return {
                "success": False,
                "error": "PIL library not installed"
            }
        
        Image, ImageGrab = pil_import
        
        try:
            screenshot = ImageGrab.grab()
            img_array = np.array(screenshot)
            
            _, buffer = cv2.imencode('.jpg', img_array)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            return {
                "success": True,
                "image": base64_image,
                "width": screenshot.width,
                "height": screenshot.height,
                "format": "jpg",
                "numpy_array": img_array
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Screen capture failed: {str(e)}"
            }
    
    def _detect_death_by_text(self, img) -> Dict:
        """通过文字检测死亡"""
        cv2 = _lazy_import_cv2()
        pytesseract = _lazy_import_tesseract()
        
        if not pytesseract:
            return {"detected": False, "method": "text", "reason": "Tesseract not available"}
        
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang='chi_sim+eng').lower()
            
            death_keywords = self._get_death_keywords()
            detected_keywords = []
            for keyword in death_keywords:
                if keyword.lower() in text:
                    detected_keywords.append(keyword)
            
            return {
                "detected": len(detected_keywords) > 0,
                "method": "text",
                "keywords": detected_keywords,
                "text": text[:200]
            }
        
        except Exception as e:
            return {"detected": False, "method": "text", "reason": str(e)}
    
    def _detect_death_by_health_bar(self, img) -> Dict:
        """通过血条区域颜色变化检测死亡"""
        np = _lazy_import_numpy()
        
        death_detection = self._get_death_detection_config()
        health_bar_config = death_detection.get("health_bar", {})
        
        if not health_bar_config.get("enabled", False):
            return {"detected": False, "method": "health_bar", "reason": "Not enabled"}
        
        region = health_bar_config.get("region")
        if not region:
            return {"detected": False, "method": "health_bar", "reason": "No region configured"}
        
        try:
            x, y, w, h = region["x"], region["y"], region["width"], region["height"]
            img_height, img_width = img.shape[:2]
            
            x = int(x * img_width / 100 if isinstance(x, float) else x)
            y = int(y * img_height / 100 if isinstance(y, float) else y)
            w = int(w * img_width / 100 if isinstance(w, float) else w)
            h = int(h * img_height / 100 if isinstance(h, float) else h)
            
            if x + w > img_width:
                w = img_width - x
            if y + h > img_height:
                h = img_height - y
            
            health_region = img[y:y+h, x:x+w]
            
            if health_region.size == 0:
                return {"detected": False, "method": "health_bar", "reason": "Invalid region"}
            
            avg_color = np.mean(health_region, axis=(0, 1))
            
            empty_color = health_bar_config.get("empty_color", [0, 0, 0])
            threshold = health_bar_config.get("threshold", 50)
            
            color_diff = np.linalg.norm(avg_color - np.array(empty_color))
            
            if color_diff < threshold:
                return {
                    "detected": True,
                    "method": "health_bar",
                    "reason": f"血条颜色接近空状态，差异: {color_diff:.2f} < 阈值: {threshold}",
                    "avg_color": avg_color.tolist(),
                    "empty_color": empty_color,
                    "diff": float(color_diff)
                }
            
            return {
                "detected": False,
                "method": "health_bar",
                "reason": f"血条颜色正常，差异: {color_diff:.2f}",
                "avg_color": avg_color.tolist()
            }
        
        except Exception as e:
            return {"detected": False, "method": "health_bar", "reason": str(e)}
    
    def _detect_death_by_scene_change(self, img) -> Dict:
        """通过画面突变检测死亡"""
        cv2 = _lazy_import_cv2()
        np = _lazy_import_numpy()
        
        death_detection = self._get_death_detection_config()
        scene_change_config = death_detection.get("scene_change", {})
        
        if not scene_change_config.get("enabled", False):
            return {"detected": False, "method": "scene_change", "reason": "Not enabled"}
        
        threshold = scene_change_config.get("threshold", 30)
        
        try:
            current_time = time.time()
            
            if self._reference_frame is None or current_time - self._reference_frame_time > self._reference_frame_interval:
                self._reference_frame = cv2.resize(img, (320, 240))
                self._reference_frame_time = current_time
                return {"detected": False, "method": "scene_change", "reason": "Updating reference frame"}
            
            current_frame_resized = cv2.resize(img, (320, 240))
            
            diff = cv2.absdiff(self._reference_frame, current_frame_resized)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, binary_diff = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            
            changed_pixels = np.sum(binary_diff == 255)
            total_pixels = binary_diff.size
            change_percent = (changed_pixels / total_pixels) * 100
            
            if change_percent > threshold:
                self._reference_frame = current_frame_resized
                self._reference_frame_time = current_time
                
                return {
                    "detected": True,
                    "method": "scene_change",
                    "reason": f"画面突变检测到 {change_percent:.2f}% 像素变化，超过阈值 {threshold}%",
                    "change_percent": float(change_percent),
                    "threshold": threshold
                }
            
            return {
                "detected": False,
                "method": "scene_change",
                "reason": f"画面变化正常: {change_percent:.2f}%",
                "change_percent": float(change_percent)
            }
        
        except Exception as e:
            return {"detected": False, "method": "scene_change", "reason": str(e)}
    
    def _detect_death_by_visual_cues(self, image_data: str) -> Dict:
        """通过LLM视觉判断检测死亡（兜底方案）"""
        death_detection = self._get_death_detection_config()
        visual_cues_config = death_detection.get("visual_cues", {})
        
        if not visual_cues_config.get("enabled", True):
            return {"detected": False, "method": "visual_cues", "reason": "Not enabled"}
        
        confidence_threshold = visual_cues_config.get("confidence_threshold", 0.7)
        chat_func = self._get_llm_chat()
        
        if not chat_func:
            return {"detected": False, "method": "visual_cues", "reason": "LLM not available"}
        
        try:
            game_name = self._current_profile.get("game_name", "Unknown") if self._current_profile else "Unknown"
            
            prompt = f"""
你是一个游戏死亡检测专家。请分析这张游戏截图，判断角色是否已经死亡或游戏是否失败。

游戏名称：{game_name}

图片内容（Base64）：{image_data[:100]}...

请回答以下问题：
1. 画面中是否显示角色死亡？
2. 是否有游戏结束画面？
3. 是否有血条清空或角色消失的迹象？
4. 是否有其他死亡相关的视觉线索？

请用JSON格式输出：
{{
    "is_dead": true/false,
    "confidence": 0.0-1.0,
    "reason": "判断原因"
}}

注意：is_dead为true表示检测到死亡，confidence表示你对判断的置信度。
"""
            
            response = chat_func(prompt, max_tokens=200)
            
            try:
                result = json.loads(response)
                is_dead = result.get("is_dead", False)
                confidence = result.get("confidence", 0.0)
                
                if is_dead and confidence >= confidence_threshold:
                    return {
                        "detected": True,
                        "method": "visual_cues",
                        "reason": f"LLM判断角色死亡，置信度: {confidence:.2f}",
                        "confidence": confidence
                    }
                
                return {
                    "detected": False,
                    "method": "visual_cues",
                    "reason": f"LLM未检测到死亡，置信度: {confidence:.2f}",
                    "confidence": confidence
                }
            
            except json.JSONDecodeError:
                return {"detected": False, "method": "visual_cues", "reason": "无法解析LLM响应"}
        
        except Exception as e:
            return {"detected": False, "method": "visual_cues", "reason": str(e)}
    
    def detect_death(self, image_data: str) -> Dict:
        """检测游戏是否失败/死亡（多层检测）"""
        cv2 = _lazy_import_cv2()
        np = _lazy_import_numpy()
        
        if not cv2 or not np:
            return {
                "success": False,
                "error": "Required libraries not installed",
                "detected": False
            }
        
        try:
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            death_detection = self._get_death_detection_config()
            enabled_methods = death_detection.get("enabled_methods", ["text", "visual_cues"])
            
            results = []
            final_detected = False
            detected_method = None
            detected_reason = ""
            
            for method in enabled_methods:
                if method == "text":
                    result = self._detect_death_by_text(img)
                elif method == "health_bar":
                    result = self._detect_death_by_health_bar(img)
                elif method == "scene_change":
                    result = self._detect_death_by_scene_change(img)
                elif method == "visual_cues":
                    result = self._detect_death_by_visual_cues(image_data)
                else:
                    continue
                
                results.append(result)
                
                if result.get("detected", False):
                    final_detected = True
                    detected_method = method
                    detected_reason = result.get("reason", "")
                    break
            
            return {
                "success": True,
                "detected": final_detected,
                "method": detected_method,
                "reason": detected_reason,
                "all_results": results,
                "enabled_methods": enabled_methods
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Death detection failed: {str(e)}",
                "detected": False
            }
    
    def _get_time_limit_config(self) -> Dict:
        """获取时间限制配置"""
        if self._current_profile:
            return self._current_profile.get("time_limit", {})
        return {}
    
    def _detect_time_limit(self, img) -> Dict:
        """检测时间限制状态"""
        cv2 = _lazy_import_cv2()
        pytesseract = _lazy_import_tesseract()
        
        time_limit_config = self._get_time_limit_config()
        
        if not time_limit_config.get("enabled", False):
            return {"detected": False, "method": "time_limit", "reason": "Not enabled"}
        
        try:
            current_time = time.time()
            total_time = time_limit_config.get("total_time", 0)
            urgency_threshold = time_limit_config.get("urgency_threshold", 30)
            
            timer_region = time_limit_config.get("timer_region")
            
            if timer_region and pytesseract:
                x, y, w, h = timer_region["x"], timer_region["y"], timer_region["width"], timer_region["height"]
                img_height, img_width = img.shape[:2]
                
                x = int(x * img_width / 100 if isinstance(x, float) else x)
                y = int(y * img_height / 100 if isinstance(y, float) else y)
                w = int(w * img_width / 100 if isinstance(w, float) else w)
                h = int(h * img_height / 100 if isinstance(h, float) else h)
                
                timer_img = img[y:y+h, x:x+w]
                gray = cv2.cvtColor(timer_img, cv2.COLOR_BGR2GRAY)
                timer_text = pytesseract.image_to_string(gray, lang='eng').strip()
                
                warning_messages = time_limit_config.get("warning_messages", [])
                for warning in warning_messages:
                    if warning.lower() in timer_text.lower():
                        return {
                            "detected": False,
                            "method": "time_limit",
                            "reason": f"检测到时间警告: {warning}",
                            "timer_text": timer_text,
                            "urgent": True
                        }
                
                import re
                time_match = re.search(r'(\d+):(\d+)', timer_text)
                if time_match:
                    minutes = int(time_match.group(1))
                    seconds = int(time_match.group(2))
                    remaining = minutes * 60 + seconds
                    self._time_limit_remaining = remaining
                    
                    if remaining <= 0:
                        return {
                            "detected": True,
                            "method": "time_limit",
                            "reason": f"时间耗尽！屏幕计时器: {timer_text}",
                            "remaining_time": 0,
                            "timer_text": timer_text,
                            "urgent": True
                        }
                    
                    if total_time > 0:
                        remaining_percent = (remaining / total_time) * 100
                        is_urgent = remaining_percent < urgency_threshold
                    else:
                        is_urgent = remaining <= 10
                    
                    return {
                        "detected": False,
                        "method": "time_limit",
                        "reason": f"计时器: {timer_text}",
                        "remaining_time": remaining,
                        "timer_text": timer_text,
                        "urgent": is_urgent
                    }
            
            if total_time > 0:
                elapsed = current_time - self._time_limit_start
                remaining = max(0, total_time - elapsed)
                remaining_percent = (remaining / total_time) * 100
                
                self._time_limit_remaining = remaining
                
                if remaining <= 0:
                    return {
                        "detected": True,
                        "method": "time_limit",
                        "reason": f"时间耗尽！总时间: {total_time}秒，已过: {elapsed:.2f}秒",
                        "remaining_time": 0,
                        "remaining_percent": 0,
                        "urgent": True
                    }
                
                if remaining_percent < urgency_threshold:
                    return {
                        "detected": False,
                        "method": "time_limit",
                        "reason": f"时间紧急！剩余: {remaining:.2f}秒 ({remaining_percent:.1f}%)",
                        "remaining_time": remaining,
                        "remaining_percent": remaining_percent,
                        "urgent": True
                    }
                
                return {
                    "detected": False,
                    "method": "time_limit",
                    "reason": f"时间正常，剩余: {remaining:.2f}秒 ({remaining_percent:.1f}%)",
                    "remaining_time": remaining,
                    "remaining_percent": remaining_percent,
                    "urgent": False
                }
            
            return {
                "detected": False,
                "method": "time_limit",
                "reason": "未配置总时间或计时器区域",
                "urgent": False
            }
        
        except Exception as e:
            return {"detected": False, "method": "time_limit", "reason": str(e), "urgent": False}
    
    def detect_time_limit(self, image_data: str = "") -> Dict:
        """检测时间限制状态（公开接口）"""
        cv2 = _lazy_import_cv2()
        np = _lazy_import_numpy()
        
        if not cv2 or not np:
            return {
                "success": False,
                "error": "Required libraries not installed",
                "detected": False
            }
        
        try:
            if image_data:
                img_bytes = base64.b64decode(image_data)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            else:
                screen_result = self.capture_screen()
                if not screen_result["success"]:
                    return screen_result
                img = screen_result["numpy_array"]
            
            return {
                "success": True,
                **self._detect_time_limit(img)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Time limit detection failed: {str(e)}",
                "detected": False
            }
    
    def move_mouse(self, x: int, y: int, duration: float = 0.1):
        """移动鼠标到指定位置"""
        pyautogui = _lazy_import_pyautogui()
        if not pyautogui:
            return False
        
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception:
            return False
    
    def click(self, button: str = 'left', clicks: int = 1, interval: float = 0.1):
        """点击鼠标"""
        pyautogui = _lazy_import_pyautogui()
        if not pyautogui:
            return False
        
        try:
            pyautogui.click(button=button, clicks=clicks, interval=interval)
            return True
        except Exception:
            return False
    
    def press_key(self, key: str, duration: float = 0.1):
        """按下并释放按键"""
        pyautogui = _lazy_import_pyautogui()
        if not pyautogui:
            return False
        
        try:
            pyautogui.keyDown(key)
            time.sleep(duration)
            pyautogui.keyUp(key)
            return True
        except Exception:
            return False
    
    def hold_key(self, key: str):
        """按住按键"""
        pyautogui = _lazy_import_pyautogui()
        if not pyautogui:
            return False
        
        try:
            pyautogui.keyDown(key)
            return True
        except Exception:
            return False
    
    def release_key(self, key: str):
        """释放按键"""
        pyautogui = _lazy_import_pyautogui()
        if not pyautogui:
            return False
        
        try:
            pyautogui.keyUp(key)
            return True
        except Exception:
            return False
    
    def _get_llm_chat(self):
        """获取LLM聊天接口"""
        try:
            from llm import chat
            return chat
        except ImportError:
            return None
    
    def analyze_game_screen(self, image_data: str) -> Dict:
        """分析游戏画面，决定下一步操作"""
        chat_func = self._get_llm_chat()
        if not chat_func:
            return {
                "success": False,
                "error": "LLM模块不可用"
            }
        
        game_name = self._current_profile.get("game_name", "Unknown") if self._current_profile else "Unknown"
        controls = self._current_profile.get("controls", []) if self._current_profile else []
        
        action_list = [c["action"] for c in controls]
        action_descriptions = "\n".join([f"- {c['action']}: {c['name']} ({c.get('description', '')})" for c in controls])
        
        try:
            prompt = f"""
你现在正在玩电脑游戏：{game_name}

请分析这张游戏截图，然后告诉我下一步应该做什么。

图片内容（Base64）：{image_data[:100]}...

当前游戏支持的操作列表：
{action_descriptions}

请提供以下信息：
1. 游戏画面分析：描述你看到的内容
2. 游戏状态：你认为当前是什么状态（正常游戏、战斗、危险、需要躲避等）
3. 建议操作：从上面的操作列表中选择一个最合适的操作

请用JSON格式输出，格式如下：
{{
    "analysis": "游戏画面分析",
    "state": "normal/danger/battle/idle",
    "action": "{action_list[0]}/{action_list[1]}/...",
    "reason": "操作原因"
}}

注意：action必须是上面操作列表中的一个
"""
            
            response = chat_func(prompt, max_tokens=300)
            
            try:
                result = json.loads(response)
                return {
                    "success": True,
                    "analysis": result.get("analysis", ""),
                    "state": result.get("state", "normal"),
                    "action": result.get("action", "do_nothing"),
                    "reason": result.get("reason", "")
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "analysis": response,
                    "state": "normal",
                    "action": "do_nothing",
                    "reason": "无法解析JSON响应"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Game analysis failed: {str(e)}"
            }
    
    def _execute_action(self, action: str):
        """执行游戏操作（根据当前配置）"""
        control = self._get_control_by_action(action)
        if not control:
            return False
        
        try:
            all_keys = self._get_all_keys()
            for key in all_keys:
                try:
                    self.release_key(key)
                except Exception:
                    pass
            
            control_type = control.get("type")
            
            if control_type == "key":
                keys = control.get("keys", [])
                if keys:
                    for key in keys:
                        self.hold_key(key)
            
            elif control_type == "mouse_click":
                button = control.get("button", "left")
                self.click(button)
            
            elif control_type == "mouse_move":
                x = control.get("x", 0)
                y = control.get("y", 0)
                self.move_mouse(x, y)
            
            return True
        except Exception:
            return False
    
    def _record_failure(self, image_data: str, analysis: str):
        """记录失败到经验模块"""
        try:
            from self_optimizer import SelfOptimizer
            optimizer = SelfOptimizer()
            optimizer.record_solve_interaction(
                f"游戏失败 - {analysis}",
                f"游戏画面分析: {analysis}",
                success=False
            )
            return True
        except Exception:
            return False
    
    def _record_to_memory(self, content: str):
        """记录到记忆模块"""
        try:
            from memory.memory import load_memory, save_memory, add
            mem = load_memory()
            add(mem, "assistant", content, source="ai_gaming")
            save_memory(mem)
            return True
        except Exception:
            return False
    
    def _game_loop(self):
        """游戏主循环"""
        self._set_game_mode(True)
        
        try:
            while self.game_running:
                if self.emergency_stop_triggered:
                    break
                
                current_time = time.time()
                if current_time - self.last_screenshot_time >= self.screenshot_interval:
                    self.last_screenshot_time = current_time
                    self.frame_count += 1
                    
                    screen_result = self.capture_screen()
                    if not screen_result["success"]:
                        continue
                    
                    self.current_frame = screen_result["image"]
                    
                    death_result = self.detect_death(self.current_frame)
                    if death_result.get("success") and death_result.get("detected"):
                        if current_time - self.last_death_time > self.death_cooldown:
                            self.death_count += 1
                            self.last_death_time = current_time
                            self.game_state = "death"
                            
                            analysis = f"检测到游戏失败！第{self.death_count}次死亡。检测方法: {death_result.get('method', 'unknown')}，原因: {death_result.get('reason', '')}"
                            print(f"[Gaming Skill] {analysis}")
                            
                            self._record_failure(self.current_frame, analysis)
                            self._record_to_memory(f"游戏失败: {analysis}")
                            
                            self.game_running = False
                            self.game_state = "stopped"
                            break
                    
                    time_limit_result = self._detect_time_limit(screen_result["numpy_array"])
                    if time_limit_result.get("detected"):
                        if current_time - self.last_death_time > self.death_cooldown:
                            self.death_count += 1
                            self.last_death_time = current_time
                            
                            analysis = f"时间耗尽！第{self.death_count}次失败。原因: {time_limit_result.get('reason', '')}"
                            print(f"[Gaming Skill] {analysis}")
                            
                            self._record_failure(self.current_frame, analysis)
                            self._record_to_memory(f"游戏失败: {analysis}")
                            
                            self.game_running = False
                            self.game_state = "stopped"
                            break
                    
                    if time_limit_result.get("urgent", False):
                        print(f"[Gaming Skill] ⚠️ 时间紧急: {time_limit_result.get('reason', '')}")
                    
                    analysis_result = self.analyze_game_screen(self.current_frame)
                    if analysis_result.get("success"):
                        action = analysis_result.get("action", "do_nothing")
                        self._execute_action(action)
                        
                        self._record_to_memory(
                            f"游戏操作: {action} - {analysis_result.get('reason', '')}"
                        )
                
                time.sleep(0.05)
        
        finally:
            self._cleanup_emergency_stop()
            self._set_game_mode(False)
            self._release_all_keys()
    
    def _release_all_keys(self):
        """释放所有按键"""
        try:
            all_keys = self._get_all_keys()
            for key in all_keys:
                try:
                    self.release_key(key)
                except Exception:
                    pass
        except Exception:
            pass
    
    def _set_game_mode(self, enabled: bool):
        """设置游戏模式（控制GAN）"""
        try:
            from thinking_engine import ThinkingEngine
            ThinkingEngine.set_game_mode(enabled)
        except Exception:
            pass
    
    def start_game(self, fps: int = 5, game_name: str = "generic") -> Dict:
        """开始游戏"""
        if self.game_running:
            return {
                "success": False,
                "error": "游戏已在运行中"
            }
        
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "error": "pyautogui未安装，请安装: pip install pyautogui"
            }
        
        profile_result = self.load_profile(game_name)
        if not profile_result["success"]:
            return profile_result
        
        self.fps = max(1, min(30, fps))
        self.screenshot_interval = 1.0 / self.fps
        self.game_running = True
        self.game_state = "playing"
        self.emergency_stop_triggered = False
        
        self._reset_death_detection_state()
        self._reset_time_limit_state()
        
        self.game_loop_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_loop_thread.start()
        
        death_methods = profile_result.get("death_detection_methods", [])
        
        return {
            "success": True,
            "message": f"游戏开始！帧率: {self.fps} FPS，游戏配置: {self._current_profile.get('game_name', 'Unknown')}",
            "fps": self.fps,
            "game_name": self._current_profile.get("game_name", "Unknown"),
            "death_detection_methods": death_methods,
            "emergency_stop": "按 Ctrl+Shift+Q 或 ESC 停止"
        }
    
    def stop_game(self) -> Dict:
        """停止游戏"""
        self.game_running = False
        self.game_state = "stopped"
        
        if self.game_loop_thread and self.game_loop_thread.is_alive():
            self.game_loop_thread.join(timeout=2)
        
        self._release_all_keys()
        
        return {
            "success": True,
            "message": "游戏已停止",
            "death_count": self.death_count,
            "frames_processed": self.frame_count
        }
    
    def get_status(self) -> Dict:
        """获取游戏状态"""
        death_methods = []
        time_limit_enabled = False
        time_limit_total = 0
        time_limit_remaining = 0
        
        if self._current_profile:
            death_detection = self._current_profile.get("death_detection", {})
            death_methods = death_detection.get("enabled_methods", [])
            
            time_limit = self._current_profile.get("time_limit", {})
            time_limit_enabled = time_limit.get("enabled", False)
            time_limit_total = time_limit.get("total_time", 0)
            time_limit_remaining = self._time_limit_remaining
        
        return {
            "game_running": self.game_running,
            "game_state": self.game_state,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "death_count": self.death_count,
            "current_game": self._current_profile.get("game_name", "Unknown") if self._current_profile else "None",
            "death_detection_methods": death_methods,
            "time_limit_enabled": time_limit_enabled,
            "time_limit_total": time_limit_total,
            "time_limit_remaining": time_limit_remaining
        }


_game_skill = None


def _get_game_skill():
    """获取游戏技能实例"""
    global _game_skill
    if _game_skill is None:
        _game_skill = GamingSkill()
    return _game_skill


def get_active_window_title() -> str:
    """获取当前活动窗口标题"""
    import sys
    
    try:
        if sys.platform == 'win32':
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow())
        elif sys.platform == 'linux':
            import subprocess
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                   capture_output=True, text=True)
            return result.stdout.strip()
        elif sys.platform == 'darwin':
            import subprocess
            result = subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of first process whose frontmost is true'],
                                   capture_output=True, text=True)
            return result.stdout.strip()
    except Exception:
        pass
    
    return ""


def detect_game_profile() -> Dict:
    """检测当前活动窗口并匹配游戏配置"""
    skill = _get_game_skill()
    window_title = get_active_window_title()
    
    if not window_title:
        return {
            "success": False,
            "error": "无法获取窗口标题"
        }
    
    profiles = skill.get_profiles()
    
    for profile_name in profiles:
        profile_path = os.path.join(skill._profiles_dir, f"{profile_name}.json")
        
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            trigger = config.get("trigger", {})
            trigger_title = trigger.get("window_title", "")
            match_mode = trigger.get("match_mode", "contains")
            
            if trigger_title:
                if match_mode == "contains" and trigger_title.lower() in window_title.lower():
                    return {
                        "success": True,
                        "detected": True,
                        "window_title": window_title,
                        "matched_profile": profile_name,
                        "game_name": config.get("game_name", ""),
                        "match_mode": match_mode
                    }
                elif match_mode == "equals" and trigger_title.lower() == window_title.lower():
                    return {
                        "success": True,
                        "detected": True,
                        "window_title": window_title,
                        "matched_profile": profile_name,
                        "game_name": config.get("game_name", ""),
                        "match_mode": match_mode
                    }
                elif match_mode == "regex":
                    import re
                    try:
                        if re.search(trigger_title, window_title, re.IGNORECASE):
                            return {
                                "success": True,
                                "detected": True,
                                "window_title": window_title,
                                "matched_profile": profile_name,
                                "game_name": config.get("game_name", ""),
                                "match_mode": match_mode
                            }
                    except re.error:
                        pass
        except Exception:
            pass
    
    return {
        "success": True,
        "detected": False,
        "window_title": window_title,
        "available_profiles": profiles
    }


def run_gui():
    """运行游戏技能配置GUI"""
    try:
        from .gui import run_gui
        run_gui()
    except ImportError:
        print("[Gaming Skill] GUI模块未找到，请确保gui.py存在")
    except Exception as e:
        print(f"[Gaming Skill] 启动GUI失败: {str(e)}")


def execute(input_data: Any) -> Dict:
    """
    执行游戏技能
    
    Args:
        input_data: 可以是字符串命令或字典
    
    支持的命令：
        - "start" / "start_game" - 开始游戏
        - "stop" / "stop_game" - 停止游戏
        - "status" / "get_status" - 获取游戏状态
        - {"action": "start", "fps": 5, "game_name": "minecraft"} - 带参数的开始
        - {"action": "load_profile", "profile": "minecraft"} - 加载游戏配置
        - {"action": "get_profiles"} - 获取可用配置列表
        - {"action": "move", "direction": "left/right/up/down"} - 移动
        - {"action": "jump"} - 跳跃
        - {"action": "attack"} - 攻击
        - {"action": "click", "x": 100, "y": 200} - 点击
        - {"action": "analyze"} - 分析当前画面
        - {"action": "detect_death"} - 检测死亡状态
    
    Returns:
        Dict with results or error
    """
    skill = _get_game_skill()
    
    action = ""
    fps = 5
    game_name = "generic"
    profile_name = ""
    direction = ""
    x, y = 0, 0
    
    if isinstance(input_data, dict):
        action = input_data.get("action", "")
        fps = input_data.get("fps", 5)
        game_name = input_data.get("game_name", "generic")
        profile_name = input_data.get("profile", "")
        direction = input_data.get("direction", "")
        x = input_data.get("x", 0)
        y = input_data.get("y", 0)
    else:
        action = str(input_data)
    
    if not action:
        return {
            "success": False,
            "error": "No action specified"
        }
    
    action = action.lower()
    
    if action in ["start", "start_game"]:
        return skill.start_game(fps=fps, game_name=game_name)
    
    elif action in ["stop", "stop_game"]:
        return skill.stop_game()
    
    elif action in ["status", "get_status"]:
        return skill.get_status()
    
    elif action == "get_profiles":
        return {
            "success": True,
            "profiles": skill.get_profiles()
        }
    
    elif action == "load_profile":
        if not profile_name:
            return {"success": False, "error": "请指定配置文件名"}
        return skill.load_profile(profile_name)
    
    elif action == "analyze":
        screen_result = skill.capture_screen()
        if not screen_result["success"]:
            return screen_result
        return skill.analyze_game_screen(screen_result["image"])
    
    elif action == "move":
        direction_map = {
            "left": "move_left",
            "right": "move_right",
            "up": "move_up",
            "down": "move_down"
        }
        dir_action = direction_map.get(direction.lower())
        if dir_action:
            skill._execute_action(dir_action)
            return {"success": True, "message": f"移动: {direction}"}
        return {"success": False, "error": f"无效方向: {direction}"}
    
    elif action == "jump":
        skill._execute_action("jump")
        return {"success": True, "message": "跳跃"}
    
    elif action == "attack":
        skill._execute_action("attack")
        return {"success": True, "message": "攻击"}
    
    elif action == "click":
        skill.click(x=x, y=y)
        return {"success": True, "message": f"点击: ({x}, {y})"}
    
    elif action == "screenshot":
        return skill.capture_screen()
    
    elif action == "detect_death":
        screen_result = skill.capture_screen()
        if not screen_result["success"]:
            return screen_result
        return skill.detect_death(screen_result["image"])
    
    elif action == "detect_time_limit":
        screen_result = skill.capture_screen()
        if not screen_result["success"]:
            return screen_result
        return skill.detect_time_limit(screen_result["image"])
    
    elif action == "detect_game":
        return detect_game_profile()
    
    elif action == "get_window_title":
        return {
            "success": True,
            "window_title": get_active_window_title()
        }
    
    elif action == "startgui":
        run_gui()
        return {"success": True, "message": "GUI已启动"}
    
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": [
                "start", "start_game",
                "stop", "stop_game",
                "status", "get_status",
                "get_profiles",
                "load_profile",
                "analyze",
                "move",
                "jump",
                "attack",
                "click",
                "screenshot",
                "detect_death",
                "detect_time_limit",
                "detect_game",
                "get_window_title",
                "startgui"
            ]
        }