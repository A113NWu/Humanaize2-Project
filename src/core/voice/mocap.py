# -*- coding: utf-8 -*-
"""
動作捕捉（面部追蹤 → Live2D 頭部姿態）

用本機攝像頭追蹤臉部位置與眼部連線角度，輸出頭部偏航/俯仰/翻滾，
由 Live2D 頁面通過 SSE 實時拉取並套用到模型參數。
無需額外模型文件（OpenCV 內置 Haar 級聯），離線可用。
"""
from __future__ import annotations

import math
import threading
import time

try:
    import cv2
except Exception:
    cv2 = None


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class MotionCapture:
    """攝像頭面部追蹤；pose 為最新姿態快照（角度制）"""

    FPS = 30

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._running = False
        self._error = ""
        self._face_found = False
        self._pose = {"x": 0.0, "y": 0.0, "z": 0.0, "body": 0.0, "face": False}
        self._jpeg = None          # 帶標註的預覽幀（MJPEG 推流用）
        self._recalibrate = False  # 下一次偵測到臉時重新校準

    def start(self) -> dict:
        if cv2 is None:
            return {"ok": False, "error": "OpenCV 未安裝"}
        with self._lock:
            if self._running:
                return {"ok": True, "already": True}
            self._stop.clear()
            self._error = ""
            self._thread = threading.Thread(target=self._loop, daemon=True, name="MotionCapture")
            self._thread.start()
            self._running = True
        return {"ok": True}

    def stop(self) -> dict:
        self._stop.set()
        with self._lock:
            self._running = False
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=3)
        with self._lock:
            self._pose = {"x": 0.0, "y": 0.0, "z": 0.0, "body": 0.0, "face": False}
            self._jpeg = None
        return {"ok": True}

    def status(self) -> dict:
        with self._lock:
            return {"running": self._running, "error": self._error,
                    "face": self._face_found, "pose": dict(self._pose)}

    def get_pose(self) -> dict:
        with self._lock:
            return dict(self._pose)

    def get_jpeg(self):
        with self._lock:
            return self._jpeg

    def recalibrate(self) -> dict:
        with self._lock:
            self._recalibrate = True
        return {"ok": True}

    # ------------------------------------------------------------------
    def _loop(self):
        cap = None
        try:
            import os
            backend = cv2.CAP_DSHOW if os.name == "nt" else 0
            cap = cv2.VideoCapture(0, backend) if backend else cv2.VideoCapture(0)
            if not cap.isOpened():
                self._error = "無法打開攝像頭（被佔用或無權限）"
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            import os as _os
            face_cascade = cv2.CascadeClassifier(
                _os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
            eye_cascade = cv2.CascadeClassifier(
                _os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))

            smooth = {"x": 0.0, "y": 0.0, "z": 0.0, "body": 0.0}
            miss = 0
            hits = 0   # 連續命中次數：Haar 誤檢較多，穩定 2 帧才採用
            center = None   # 首次穩定偵測的位置作為「正對鏡頭」基準（自動校準）
            interval = 1.0 / self.FPS
            frame_no = 0
            while not self._stop.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(interval)
                    continue
                frame = cv2.flip(frame, 1)   # 鏡像，符合用戶照鏡子的直覺
                h, w = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.15, 6, minSize=(110, 110))

                frame_no += 1
                target = {"x": 0.0, "y": 0.0, "z": 0.0, "body": 0.0}
                rect = None
                found = len(faces) > 0
                if found:
                    miss = 0
                    hits += 1
                else:
                    miss += 1
                    hits = 0
                if found and hits >= 2:
                    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
                    rect = (x, y, fw, fh)
                    cx = (x + fw / 2.0) / w
                    cy = (y + fh / 2.0) / h
                    if center is None:
                        # 自動校準：用戶當前的坐姿即為「正對鏡頭」
                        center = (cx, cy)
                    # 相對校準點的偏移 → 頭部左右/上下轉動
                    target["x"] = _clamp((cx - center[0]) * 100.0, -30, 30)
                    target["y"] = _clamp((center[1] - cy) * 100.0, -30, 30)
                    target["body"] = _clamp(target["x"] * 0.28, -10, 10)
                    # 眼部連線角度 → 頭部翻滾
                    roi = gray[y:y + fh // 2, x:x + fw]
                    eyes = eye_cascade.detectMultiScale(roi, 1.1, 5, minSize=(20, 20))
                    if len(eyes) >= 2:
                        eyes = sorted(eyes, key=lambda e: e[0])[:2]
                        e1, e2 = eyes
                        p1 = (e1[0] + e1[2] / 2.0, e1[1] + e1[3] / 2.0)
                        p2 = (e2[0] + e2[2] / 2.0, e2[1] + e2[3] / 2.0)
                        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
                        target["z"] = _clamp(ang * 1.2, -30, 30)

                accepted = found and hits >= 2
                if miss > 90:
                    center = None   # 離開約 3 秒後重新校準，避免坐姿改變造成偏移
                with self._lock:
                    if self._recalibrate:
                        self._recalibrate = False
                        center = None
                if accepted or miss > 12:
                    a = 0.2  # 指數平滑，動作不生硬
                    for k in smooth:
                        smooth[k] += (target[k] - smooth[k]) * a

                pose_now = {"x": round(smooth["x"], 2), "y": round(smooth["y"], 2),
                            "z": round(smooth["z"], 2), "body": round(smooth["body"], 2),
                            "face": accepted}
                with self._lock:
                    self._face_found = accepted
                    self._pose = pose_now

                # 預覽幀（約 15fps，帶人臉框與姿態數值）
                if frame_no % 2 == 0:
                    vis = frame.copy()
                    if rect:
                        bx, by, bw2, bh2 = rect
                        cv2.rectangle(vis, (bx, by), (bx + bw2, by + bh2), (74, 222, 128), 2)
                    label = f"X {pose_now['x']:.1f}  Y {pose_now['y']:.1f}  Z {pose_now['z']:.1f}"
                    if not accepted:
                        label = "未檢測到面部 - " + label
                    cv2.putText(vis, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (74, 222, 128) if accepted else (120, 120, 120), 2)
                    vis = cv2.resize(vis, (480, int(480 * h / w)))
                    okj, buf = cv2.imencode(".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
                    if okj:
                        with self._lock:
                            self._jpeg = buf.tobytes()

                dt = interval - (time.time() - t0)
                if dt > 0:
                    time.sleep(dt)
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            with self._lock:
                self._running = False


_instance = None
_instance_lock = threading.Lock()


def get_motion_capture() -> MotionCapture:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MotionCapture()
    return _instance
