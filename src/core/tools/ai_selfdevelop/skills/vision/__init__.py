#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像识别技能执行模块
"""

import os
import sys
import base64
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from src.core.llm.llm import chat
    HAS_LLM = True
except ImportError:
    HAS_LLM = False


def _load_image(image_path: str = None, image_base64: str = None) -> Optional[Image.Image]:
    """加载图片"""
    if not HAS_PIL:
        return None
    
    try:
        if image_path and os.path.exists(image_path):
            return Image.open(image_path)
        elif image_base64:
            import io
            image_data = base64.b64decode(image_base64)
            return Image.open(io.BytesIO(image_data))
    except Exception as e:
        print(f"Failed to load image: {e}")
    
    return None


def _image_to_base64(image: Image.Image) -> str:
    """将图片转换为base64"""
    import io
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def analyze_image(image_path: str = None, image_base64: str = None) -> Dict:
    """分析图片内容"""
    image = _load_image(image_path, image_base64)
    if not image:
        return {"status": "error", "message": "Failed to load image or PIL not available"}
    
    result = {
        "status": "success",
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "format": image.format or "JPEG"
    }
    
    try:
        text = pytesseract.image_to_string(image, lang='chi_sim+eng') if HAS_TESSERACT else ""
        result["ocr_text"] = text.strip() if text else None
    except Exception as e:
        result["ocr_text"] = None
        result["ocr_error"] = str(e)
    
    if HAS_LLM and (image_path or image_base64):
        try:
            prompt = f"""请分析以下图片内容：
图片尺寸: {image.width}x{image.height}
图片格式: {image.format}
OCR识别文字: {result.get('ocr_text', '无')}

请描述图片中的内容，包括：
1. 主要物体和场景
2. 图片中的文字内容（如果有）
3. 图片的整体主题和氛围

请用中文回答，尽量详细。"""
            
            llm_response = chat(prompt)
            result["analysis"] = llm_response
        except Exception as e:
            result["analysis"] = None
            result["analysis_error"] = str(e)
    
    return result


def ocr_image(image_path: str = None, image_base64: str = None) -> Dict:
    """识别图片中的文字"""
    if not HAS_TESSERACT:
        return {"status": "error", "message": "pytesseract not available"}
    
    image = _load_image(image_path, image_base64)
    if not image:
        return {"status": "error", "message": "Failed to load image"}
    
    try:
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        return {
            "status": "success",
            "text": text.strip(),
            "confidence": "high" if len(text.strip()) > 0 else "low"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def describe_image(image_path: str = None, image_base64: str = None) -> Dict:
    """描述图片内容"""
    if not HAS_LLM:
        return {"status": "error", "message": "LLM not available"}
    
    image = _load_image(image_path, image_base64)
    if not image:
        return {"status": "error", "message": "Failed to load image"}
    
    ocr_text = ""
    if HAS_TESSERACT:
        try:
            ocr_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        except:
            ocr_text = ""
    
    try:
        prompt = f"""请详细描述这张图片的内容。

图片信息：
- 尺寸: {image.width}x{image.height}
- 格式: {image.format}
- OCR识别文字: {ocr_text if ocr_text else '未识别到文字'}

请从以下几个方面进行描述：
1. 图片中的主要物体、人物或场景
2. 图片的颜色和构图特点
3. 图片传达的情感或主题
4. 如果有文字，请说明文字内容和含义

请用中文回答，语言要生动形象。"""
        
        response = chat(prompt)
        return {"status": "success", "description": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def detect_objects(image_path: str = None, image_base64: str = None) -> Dict:
    """检测图片中的物体"""
    if not HAS_LLM:
        return {"status": "error", "message": "LLM not available"}
    
    image = _load_image(image_path, image_base64)
    if not image:
        return {"status": "error", "message": "Failed to load image"}
    
    try:
        prompt = f"""请分析这张图片，识别图片中包含的物体。

图片尺寸: {image.width}x{image.height}

请列出你识别到的所有物体，包括：
- 人物（性别、年龄、动作等）
- 动物
- 物品（家具、电器、交通工具等）
- 场景（室内、室外、自然景观等）

请用中文回答，格式为列表形式。"""
        
        response = chat(prompt)
        return {"status": "success", "objects": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def extract_text(image_path: str = None, image_base64: str = None) -> Dict:
    """提取图片中的文字"""
    return ocr_image(image_path, image_base64)


def execute(input_data: Any) -> dict:
    """执行图像识别技能"""
    if isinstance(input_data, dict):
        action = input_data.get('action', '')
        params = input_data.get('params', {})
        image_data = input_data.get('image', '')
        
        image_path = params.get('image_path', '') or input_data.get('image_path', '')
        image_base64 = params.get('image_base64', '') or input_data.get('image_base64', '')
    else:
        action = str(input_data)
        params = {}
        image_path = ''
        image_base64 = ''
        image_data = ''
    
    if image_data and not image_path and not image_base64:
        image_base64 = image_data
    
    if action == 'analyze':
        return analyze_image(image_path, image_base64)
    
    elif action == 'ocr':
        return ocr_image(image_path, image_base64)
    
    elif action == 'describe':
        return describe_image(image_path, image_base64)
    
    elif action == 'detect_objects':
        return detect_objects(image_path, image_base64)
    
    elif action == 'extract_text':
        return extract_text(image_path, image_base64)
    
    elif action == 'recognize_text':
        return ocr_image(image_path, image_base64)
    
    elif action == 'capture_screen':
        try:
            from PIL import ImageGrab
            screen = ImageGrab.grab()
            import io
            buffer = io.BytesIO()
            screen.save(buffer, format='JPEG')
            screen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return {"success": True, "image": screen_base64}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == 'start_camera':
        return {"success": False, "error": "Camera not supported in this module. Use core vision skill."}
    
    elif action == 'stop_camera':
        return {"success": False, "error": "Camera not supported in this module."}
    
    elif action == 'capture_frame':
        return {"success": False, "error": "Camera not supported in this module."}
    
    elif action == 'screen_analyze':
        try:
            from PIL import ImageGrab
            screen = ImageGrab.grab()
            import io
            buffer = io.BytesIO()
            screen.save(buffer, format='JPEG')
            screen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return analyze_image(image_base64=screen_base64)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == 'ai_analyze':
        return analyze_image(image_path, image_base64)
    
    elif action == 'show_camera':
        return {"success": False, "error": "Camera not supported in this module."}
    
    elif action == 'camera_analyze':
        return {"success": False, "error": "Camera not supported in this module."}
    
    elif action == 'full_analyze':
        result = analyze_image(image_path, image_base64)
        if result.get('status') == 'success':
            return {
                "success": True,
                "analysis": result.get('analysis', ''),
                "ocr_text": result.get('ocr_text', ''),
                "objects": result.get('analysis', '')
            }
        return result
    
    elif action == 'screen_full_analyze':
        try:
            from PIL import ImageGrab
            screen = ImageGrab.grab()
            import io
            buffer = io.BytesIO()
            screen.save(buffer, format='JPEG')
            screen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            result = analyze_image(image_base64=screen_base64)
            if result.get('status') == 'success':
                return {
                    "success": True,
                    "analysis": result.get('analysis', ''),
                    "ocr_text": result.get('ocr_text', '')
                }
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == 'camera_full_analyze':
        return {"success": False, "error": "Camera not supported in this module."}
    
    elif action == 'show_analysis':
        return {"success": False, "error": "Visual display not supported in this module."}
    
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}
