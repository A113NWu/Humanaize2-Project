"""
Humanaize Detect Emotion Skill
Analyze facial expressions to detect user emotions
"""

import cv2
from typing import Dict, Any
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False


def execute(input_data: Any = None) -> Dict:
    """
    Detect user emotion from camera

    Args:
        input_data: Optional dict with 'camera' key (default: 0)

    Returns:
        Dict with dominant emotion, confidence, and detailed emotions
    """
    if not DEEPFACE_AVAILABLE:
        return {
            "success": False,
            "error": "deepface library not installed. Install with: pip install deepface opencv-python",
            "dominant": "unknown",
            "confidence": 0.0
        }

    camera_index = 0
    if isinstance(input_data, dict):
        camera_index = input_data.get("camera", 0)

    cap = None
    try:
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            return {
                "success": False,
                "error": "Cannot access camera",
                "dominant": "unknown",
                "confidence": 0.0
            }

        ret, frame = cap.read()
        cap.release()
        cap = None

        if not ret or frame is None:
            return {
                "success": False,
                "error": "Failed to capture frame from camera",
                "dominant": "unknown",
                "confidence": 0.0
            }

        result_list = DeepFace.analyze(
            frame,
            actions=['emotion'],
            enforce_detection=False,
            silent=True
        )

        if isinstance(result_list, list) and len(result_list) > 0:
            result = result_list[0]
        elif isinstance(result_list, dict):
            result = result_list
        else:
            return {
                "success": False,
                "error": "Unexpected result from DeepFace",
                "dominant": "unknown",
                "confidence": 0.0
            }

        dominant = result.get("dominant_emotion", result.get("dominant", "neutral"))
        emotions = result.get("emotion", {})

        if isinstance(emotions, dict):
            confidence = max(emotions.values()) if emotions else 0.0
            emotion_scores = {k: float(v) for k, v in emotions.items()}
        else:
            confidence = 0.0
            emotion_scores = {}

        return {
            "success": True,
            "dominant": dominant,
            "confidence": float(confidence),
            "emotions": emotion_scores,
            "face_detected": result.get("face_detected", True) if isinstance(result, dict) else True
        }

    except cv2.error as e:
        return {
            "success": False,
            "error": f"OpenCV error: {str(e)}",
            "dominant": "unknown",
            "confidence": 0.0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Emotion detection failed: {str(e)}",
            "dominant": "unknown",
            "confidence": 0.0
        }
    finally:
        if cap is not None and cap.isOpened():
            cap.release()


def analyze_image(image_path: str) -> Dict:
    """
    Analyze emotion from an image file

    Args:
        image_path: Path to image file

    Returns:
        Dict with emotion analysis results
    """
    if not DEEPFACE_AVAILABLE:
        return {
            "success": False,
            "error": "deepface library not installed"
        }

    if not image_path:
        return {
            "success": False,
            "error": "No image path provided"
        }

    try:
        result_list = DeepFace.analyze(
            img_path=image_path,
            actions=['emotion'],
            enforce_detection=False,
            silent=True
        )

        if isinstance(result_list, list) and len(result_list) > 0:
            result = result_list[0]
        else:
            result = result_list

        dominant = result.get("dominant_emotion", "neutral")
        emotions = result.get("emotion", {})

        return {
            "success": True,
            "dominant": dominant,
            "emotions": emotions,
            "image_path": image_path
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
