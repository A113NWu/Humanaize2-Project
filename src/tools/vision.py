import cv2
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
from threading import Thread
from time import sleep
from config import SCREENSHOT_INTERVAL

class VisionThread(Thread):
    def __init__(self, emotion_callback):
        super().__init__(daemon=True)
        self.emotion_callback = emotion_callback
        self.running = True

    def run(self):
        if not DEEPFACE_AVAILABLE:
            return

        while self.running:
            cap = cv2.VideoCapture(0)
            try:
                if not cap.isOpened():
                    break
                ret, frame = cap.read()
                if ret and frame is not None:
                    try:
                        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
                        if isinstance(result, list):
                            r = result[0] if result else {}
                        else:
                            r = result or {}

                        dominant = None
                        confidence = None
                        if isinstance(r, dict):
                            dominant = r.get("dominant_emotion") or r.get("dominant")
                            emo = r.get("emotion")
                            if isinstance(emo, dict):
                                confidence = max(emo.values()) if emo else None

                        if not dominant:
                            dominant = "neutral"

                        data = {"dominant": dominant}
                        if confidence is not None:
                            try:
                                data["confidence"] = float(confidence)
                            except Exception:
                                pass

                        self.emotion_callback(data)
                    except Exception:
                        try:
                            self.emotion_callback({"dominant": "neutral", "confidence": 0.0})
                        except Exception:
                            pass
            finally:
                try:
                    cap.release()
                except Exception:
                    pass

            for _ in range(int(max(1, SCREENSHOT_INTERVAL * 2))):
                if not self.running:
                    break
                sleep(0.5)

    def stop(self):
        self.running = False
