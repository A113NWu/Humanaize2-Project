# -*- coding: utf-8 -*-
"""
Humanaize Vision Skill - AI视觉交互技能

功能：
1. 屏幕捕获 - 获取当前屏幕显示内容
2. 摄像头调用 - 激活设备摄像头获取实时画面
3. 图像识别 - 物体识别、场景理解和文本识别
4. 视觉窗口 - 显示识别结果和高亮标记
"""

import os
import sys
import json
import base64
from typing import Dict, Any, Optional

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


class VisionEngine:
    """视觉引擎 - 处理所有视觉相关操作"""
    
    def __init__(self):
        self.camera = None
        self.camera_active = False
        self.screen_capture_active = False
        self.detection_results = []
    
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


# 全局视觉引擎实例
_vision_engine = VisionEngine()


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
        - {"action": "...", "image": "..."} - 带参数的操作
    
    Returns:
        Dict with results or error
    """
    global _vision_engine
    
    if isinstance(input_data, dict):
        action = input_data.get("action", "")
        image_data = input_data.get("image", "")
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
                "screen_analyze",
                "camera_analyze"
            ]
        }
