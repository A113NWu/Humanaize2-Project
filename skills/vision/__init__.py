# -*- coding: utf-8 -*-
"""
Humanaize Vision Skill - AI视觉交互技能

功能：
1. 屏幕捕获 - 获取当前屏幕显示内容
2. 摄像头调用 - 激活设备摄像头获取实时画面
3. 图像识别 - 物体识别、场景理解和文本识别
4. 视觉窗口 - 显示识别结果和高亮标记
5. AI图像分析 - 调用LLM分析图像内容
"""

import os
import sys
import json
import base64
import threading
import time
from typing import Dict, Any, Optional, List

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from PIL import Image, ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import ttk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


class VisionEngine:
    """视觉引擎 - 处理所有视觉相关操作"""
    
    def __init__(self):
        self.camera = None
        self.camera_active = False
        self.screen_capture_active = False
        self.detection_results = []
        self.analysis_window = None
        self.stream_thread = None
        self.stream_running = False
    
    def _get_llm_chat(self):
        """获取LLM聊天接口"""
        try:
            from llm import chat
            return chat
        except ImportError:
            return None
    
    def ai_analyze_image(self, image_data: str, question: str = "") -> Dict:
        """
        使用AI分析图像内容
        
        Args:
            image_data: Base64编码的图像数据
            question: 用户问题（可选）
            
        Returns:
            Dict with AI analysis results
        """
        chat_func = self._get_llm_chat()
        if not chat_func:
            return {
                "success": False,
                "error": "LLM模块不可用"
            }
        
        try:
            prompt = f"""
请分析这张图片。

图片内容（Base64）：{image_data[:50]}...

{"用户问题：" + question if question else ""}

请提供以下信息：
1. 图像中识别到的主要物体和场景
2. 关键文本内容（如果有）
3. 对用户问题的回答（如果有）
4. 相关问题的解决方案（如果适用）

请用简洁的中文回答。
"""
            
            response = chat_func(prompt, max_tokens=500)
            
            return {
                "success": True,
                "analysis": response.strip(),
                "method": "llm"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"AI图像分析失败: {str(e)}"
            }
    
    def capture_screen(self) -> Dict:
        """
        捕获当前屏幕内容
        
        Returns:
            Dict with screen image data or error
        """
        if not PIL_AVAILABLE:
            return {
                "success": False,
                "error": "PIL library not installed. Install with: pip install pillow"
            }
        
        try:
            screenshot = ImageGrab.grab()
            img_array = np.array(screenshot)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            _, buffer = cv2.imencode('.jpg', img_array)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            return {
                "success": True,
                "image": base64_image,
                "width": screenshot.width,
                "height": screenshot.height,
                "format": "jpg",
                "source": "screen"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Screen capture failed: {str(e)}"
            }
    
    def start_camera(self) -> Dict:
        """
        启动摄像头
        
        Returns:
            Dict with camera status
        """
        if not CV2_AVAILABLE:
            return {
                "success": False,
                "error": "OpenCV not installed. Install with: pip install opencv-python"
            }
        
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                return {
                    "success": False,
                    "error": "无法打开摄像头"
                }
            
            self.camera_active = True
            return {
                "success": True,
                "message": "摄像头已启动",
                "width": int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"启动摄像头失败: {str(e)}"
            }
    
    def stop_camera(self) -> Dict:
        """
        停止摄像头
        
        Returns:
            Dict with status
        """
        try:
            if self.camera and self.camera_active:
                self.camera.release()
                self.camera_active = False
            
            return {
                "success": True,
                "message": "摄像头已停止"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"停止摄像头失败: {str(e)}"
            }
    
    def capture_camera_frame(self) -> Dict:
        """
        捕获摄像头当前帧
        
        Returns:
            Dict with frame image data
        """
        if not CV2_AVAILABLE or not self.camera_active or not self.camera:
            return {
                "success": False,
                "error": "摄像头未启动"
            }
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                return {
                    "success": False,
                    "error": "无法读取摄像头帧"
                }
            
            _, buffer = cv2.imencode('.jpg', frame)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            return {
                "success": True,
                "image": base64_image,
                "source": "camera"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"捕获帧失败: {str(e)}"
            }
    
    def recognize_text(self, image_data: str) -> Dict:
        """
        识别图像中的文本（OCR）
        
        Args:
            image_data: Base64编码的图像数据
        
        Returns:
            Dict with text recognition results
        """
        if not TESSERACT_AVAILABLE:
            return {
                "success": False,
                "error": "Tesseract not installed. Install with: pip install pytesseract"
            }
        
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {
                "success": False,
                "error": "OpenCV or NumPy not installed"
            }
        
        try:
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang='chi_sim+eng')
            
            data = pytesseract.image_to_data(gray, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
            
            bounding_boxes = []
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 60 and data['text'][i].strip():
                    (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                    bounding_boxes.append({
                        "text": data['text'][i].strip(),
                        "confidence": int(data['conf'][i]),
                        "bbox": {"x": x, "y": y, "width": w, "height": h}
                    })
            
            return {
                "success": True,
                "text": text.strip(),
                "bounding_boxes": bounding_boxes,
                "method": "tesseract"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"文本识别失败: {str(e)}"
            }
    
    def detect_objects(self, image_data: str) -> Dict:
        """
        检测图像中的物体
        
        Args:
            image_data: Base64编码的图像数据
        
        Returns:
            Dict with object detection results
        """
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return {
                "success": False,
                "error": "OpenCV or NumPy not installed"
            }
        
        try:
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 50, 150)
            
            contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            objects = []
            for contour in contours:
                if cv2.contourArea(contour) > 100:
                    x, y, w, h = cv2.boundingRect(contour)
                    objects.append({
                        "bbox": {"x": x, "y": y, "width": w, "height": h},
                        "area": int(cv2.contourArea(contour))
                    })
            
            return {
                "success": True,
                "objects": objects,
                "count": len(objects),
                "method": "cv2_contour"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"物体检测失败: {str(e)}"
            }
    
    def analyze_image(self, image_data: str) -> Dict:
        """
        综合分析图像（文本识别 + 物体检测）
        
        Args:
            image_data: Base64编码的图像数据
        
        Returns:
            Dict with comprehensive analysis results
        """
        results = {
            "success": True,
            "text_recognition": None,
            "object_detection": None,
            "highlight_boxes": []
        }
        
        text_result = self.recognize_text(image_data)
        if text_result["success"]:
            results["text_recognition"] = text_result
            for box in text_result.get("bounding_boxes", []):
                results["highlight_boxes"].append({
                    "type": "text",
                    "label": box["text"],
                    "bbox": box["bbox"],
                    "confidence": box["confidence"]
                })
        
        object_result = self.detect_objects(image_data)
        if object_result["success"]:
            results["object_detection"] = object_result
            for obj in object_result.get("objects", []):
                results["highlight_boxes"].append({
                    "type": "object",
                    "label": "物体",
                    "bbox": obj["bbox"],
                    "confidence": 0.7
                })
        
        return results
    
    def show_analysis_window(self, image_data: str, analysis_results: Dict):
        """
        显示视觉分析窗口
        
        Args:
            image_data: Base64编码的图像数据
            analysis_results: 分析结果
        """
        if not TKINTER_AVAILABLE:
            return {
                "success": False,
                "error": "Tkinter not available"
            }
        
        if self.analysis_window and self.analysis_window.winfo_exists():
            self.analysis_window.destroy()
        
        try:
            root = tk.Toplevel()
            root.title("Humanaize Vision Analysis")
            root.geometry("900x600")
            root.minsize(800, 500)
            
            self.analysis_window = root
            
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            highlight_boxes = analysis_results.get("highlight_boxes", [])
            for box in highlight_boxes:
                bbox = box["bbox"]
                cv2.rectangle(img_rgb, 
                            (bbox["x"], bbox["y"]), 
                            (bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]), 
                            (0, 255, 0), 2)
                
                label = box.get("label", "")[:20]
                cv2.putText(img_rgb, label, 
                            (bbox["x"], bbox["y"] - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            img_pil = Image.fromarray(img_rgb)
            
            from PIL import ImageTk
            img_tk = ImageTk.PhotoImage(img_pil)
            
            main_frame = ttk.Frame(root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            image_label = ttk.Label(scrollable_frame, image=img_tk)
            image_label.image = img_tk
            image_label.pack(pady=(0, 10))
            
            results_frame = ttk.LabelFrame(scrollable_frame, text="分析结果")
            results_frame.pack(fill=tk.X, pady=(0, 10))
            
            text_result = analysis_results.get("text_recognition")
            if text_result and text_result.get("success"):
                text_label = ttk.Label(results_frame, text="识别文本:", font=("Arial", 10, "bold"))
                text_label.pack(anchor="w", padx=5, pady=(5, 2))
                
                text_content = text_result.get("text", "")
                text_text = tk.Text(results_frame, height=4, wrap=tk.WORD)
                text_text.insert(tk.END, text_content if text_content else "无文本")
                text_text.configure(state="disabled")
                text_text.pack(fill=tk.X, padx=5, pady=(0, 5))
            
            object_result = analysis_results.get("object_detection")
            if object_result and object_result.get("success"):
                obj_label = ttk.Label(results_frame, text="检测物体:", font=("Arial", 10, "bold"))
                obj_label.pack(anchor="w", padx=5, pady=(5, 2))
                
                obj_count = object_result.get("count", 0)
                obj_text = ttk.Label(results_frame, text=f"共检测到 {obj_count} 个物体")
                obj_text.pack(anchor="w", padx=5, pady=(0, 5))
            
            ai_result = analysis_results.get("ai_analysis")
            if ai_result and ai_result.get("success"):
                ai_label = ttk.Label(results_frame, text="AI分析:", font=("Arial", 10, "bold"))
                ai_label.pack(anchor="w", padx=5, pady=(5, 2))
                
                ai_text = tk.Text(results_frame, height=6, wrap=tk.WORD)
                ai_text.insert(tk.END, ai_result.get("analysis", ""))
                ai_text.configure(state="disabled")
                ai_text.pack(fill=tk.X, padx=5, pady=(0, 5))
            
            close_btn = ttk.Button(root, text="关闭", command=root.destroy)
            close_btn.pack(pady=(0, 10))
            
            return {
                "success": True,
                "message": "分析窗口已显示"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"显示分析窗口失败: {str(e)}"
            }


class VisionStreamWindow:
    """视觉流窗口 - 显示摄像头实时画面"""
    
    def __init__(self, vision_engine: VisionEngine):
        self.vision_engine = vision_engine
        self.window = None
        self.label = None
        self.running = False
    
    def show(self):
        """显示摄像头流窗口"""
        if not CV2_AVAILABLE or not TKINTER_AVAILABLE:
            return
        
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        
        root = tk.Toplevel()
        root.title("Humanaize Camera Stream")
        root.geometry("640x480")
        root.protocol("WM_DELETE_WINDOW", self.close)
        
        self.window = root
        self.label = ttk.Label(root)
        self.label.pack(fill=tk.BOTH, expand=True)
        
        self.running = True
        self.update_frame()
    
    def update_frame(self):
        """更新摄像头帧"""
        if not self.running or not self.window:
            return
        
        frame_result = self.vision_engine.capture_camera_frame()
        if frame_result.get("success"):
            try:
                image_data = frame_result["image"]
                img_bytes = base64.b64decode(image_data)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                
                from PIL import ImageTk
                img_pil = Image.fromarray(img_rgb)
                img_tk = ImageTk.PhotoImage(img_pil)
                
                self.label.configure(image=img_tk)
                self.label.image = img_tk
            except Exception:
                pass
        
        if self.running:
            self.window.after(30, self.update_frame)
    
    def close(self):
        """关闭窗口"""
        self.running = False
        if self.window:
            self.window.destroy()
            self.window = None


# 全局视觉引擎实例
_vision_engine = VisionEngine()
_stream_window = None


def execute(input_data: Any) -> Dict:
    """
    执行视觉技能
    
    Args:
        input_data: 可以是字符串命令或字典
    
    支持的命令：
        - "capture_screen" - 捕获屏幕
        - "start_camera" - 启动摄像头
        - "stop_camera" - 停止摄像头
        - "capture_frame" - 捕获摄像头帧
        - "recognize_text" - 识别文本（需要image参数）
        - "detect_objects" - 检测物体（需要image参数）
        - "analyze" - 综合分析（需要image参数）
        - "ai_analyze" - AI分析图像（需要image参数，可选question）
        - "show_camera" - 显示摄像头实时窗口
        - "screen_analyze" - 捕获屏幕并分析
        - "camera_analyze" - 使用摄像头分析
        - "full_analyze" - 完整分析（AI + OCR + 物体检测）
        - {"action": "...", "image": "...", "question": "..."} - 带参数的操作
    
    Returns:
        Dict with results or error
    """
    global _vision_engine, _stream_window
    
    question = ""
    if isinstance(input_data, dict):
        action = input_data.get("action", "")
        image_data = input_data.get("image", "")
        question = input_data.get("question", "")
    else:
        action = str(input_data)
        image_data = ""
    
    if not action:
        return {
            "success": False,
            "error": "No action specified"
        }
    
    action = action.lower()
    
    if action == "capture_screen":
        return _vision_engine.capture_screen()
    
    elif action == "start_camera":
        return _vision_engine.start_camera()
    
    elif action == "stop_camera":
        return _vision_engine.stop_camera()
    
    elif action == "capture_frame":
        return _vision_engine.capture_camera_frame()
    
    elif action == "recognize_text":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for text recognition"
            }
        return _vision_engine.recognize_text(image_data)
    
    elif action == "detect_objects":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for object detection"
            }
        return _vision_engine.detect_objects(image_data)
    
    elif action == "analyze":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for analysis"
            }
        return _vision_engine.analyze_image(image_data)
    
    elif action == "ai_analyze":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for AI analysis"
            }
        return _vision_engine.ai_analyze_image(image_data, question)
    
    elif action == "show_camera":
        start_result = _vision_engine.start_camera()
        if not start_result["success"]:
            return start_result
        
        if _stream_window:
            _stream_window.close()
        
        _stream_window = VisionStreamWindow(_vision_engine)
        
        def run_window():
            try:
                _stream_window.show()
            except Exception:
                pass
        
        thread = threading.Thread(target=run_window, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "message": "摄像头窗口已打开"
        }
    
    elif action == "screen_analyze":
        screen_result = _vision_engine.capture_screen()
        if not screen_result["success"]:
            return screen_result
        return _vision_engine.analyze_image(screen_result["image"])
    
    elif action == "camera_analyze":
        start_result = _vision_engine.start_camera()
        if not start_result["success"]:
            return start_result
        
        frame_result = _vision_engine.capture_camera_frame()
        if not frame_result["success"]:
            _vision_engine.stop_camera()
            return frame_result
        
        analyze_result = _vision_engine.analyze_image(frame_result["image"])
        _vision_engine.stop_camera()
        
        return {
            "success": True,
            "source": "camera",
            **analyze_result
        }
    
    elif action == "full_analyze":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for full analysis"
            }
        
        results = {
            "success": True,
            "source": "image",
            "text_recognition": None,
            "object_detection": None,
            "ai_analysis": None,
            "highlight_boxes": []
        }
        
        text_result = _vision_engine.recognize_text(image_data)
        if text_result["success"]:
            results["text_recognition"] = text_result
            for box in text_result.get("bounding_boxes", []):
                results["highlight_boxes"].append({
                    "type": "text",
                    "label": box["text"],
                    "bbox": box["bbox"],
                    "confidence": box["confidence"]
                })
        
        object_result = _vision_engine.detect_objects(image_data)
        if object_result["success"]:
            results["object_detection"] = object_result
            for obj in object_result.get("objects", []):
                results["highlight_boxes"].append({
                    "type": "object",
                    "label": "物体",
                    "bbox": obj["bbox"],
                    "confidence": 0.7
                })
        
        ai_result = _vision_engine.ai_analyze_image(image_data, question)
        if ai_result["success"]:
            results["ai_analysis"] = ai_result
        
        return results
    
    elif action == "screen_full_analyze":
        screen_result = _vision_engine.capture_screen()
        if not screen_result["success"]:
            return screen_result
        
        return execute({
            "action": "full_analyze",
            "image": screen_result["image"],
            "question": question
        })
    
    elif action == "camera_full_analyze":
        start_result = _vision_engine.start_camera()
        if not start_result["success"]:
            return start_result
        
        frame_result = _vision_engine.capture_camera_frame()
        if not frame_result["success"]:
            _vision_engine.stop_camera()
            return frame_result
        
        _vision_engine.stop_camera()
        
        return execute({
            "action": "full_analyze",
            "image": frame_result["image"],
            "question": question
        })
    
    elif action == "show_analysis":
        if not image_data:
            return {
                "success": False,
                "error": "No image data provided for showing analysis"
            }
        
        analyze_result = _vision_engine.analyze_image(image_data)
        ai_result = _vision_engine.ai_analyze_image(image_data, question)
        if ai_result["success"]:
            analyze_result["ai_analysis"] = ai_result
        
        window_result = _vision_engine.show_analysis_window(image_data, analyze_result)
        
        return {
            "success": True,
            "analysis": analyze_result,
            "window": window_result
        }
    
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": [
                "capture_screen",
                "start_camera",
                "stop_camera",
                "capture_frame",
                "recognize_text",
                "detect_objects",
                "analyze",
                "ai_analyze",
                "show_camera",
                "screen_analyze",
                "camera_analyze",
                "full_analyze",
                "screen_full_analyze",
                "camera_full_analyze",
                "show_analysis"
            ]
        }
