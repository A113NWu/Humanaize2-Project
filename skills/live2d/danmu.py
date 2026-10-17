"""
B站直播間彈幕客戶端

連接 B 站直播彈幕 WebSocket，收到彈幕後調 live2d_hub.ingest_chat()，
Live2D 頁面輪詢拿到 chat_in 再轉引擎回復，形成直播互動閉環。
依賴 websockets + brotli（缺失時 danmu_start 會報錯提示）。
"""

import json
import struct
import asyncio
import threading

_WS_URL = "wss://broadcastlv.chat.bilibili.com:2245/sub"

_client = None
_client_lock = threading.Lock()


def _pack(op, body=b""):
    header = struct.pack(">IHHII", 16 + len(body), 16, 1, op, 1)
    return header + body


def _parse_packets(data, on_json):
    offset = 0
    while offset + 16 <= len(data):
        total, head_len, ver, op, seq = struct.unpack(">IHHII", data[offset:offset + 16])
        body = data[offset + head_len:offset + total]
        if ver == 2:
            try:
                import brotli
                _parse_packets(brotli.decompress(body), on_json)
            except Exception:
                pass
        elif op == 5 and body:
            try:
                on_json(json.loads(body.decode("utf-8", "ignore")))
            except Exception:
                pass
        offset += total if total > 0 else len(data)


async def _run(room_id, on_danmu, on_log):
    import websockets
    auth = _pack(7, json.dumps({
        "uid": 0, "roomid": int(room_id), "protover": 2,
        "platform": "web", "type": 2, "key": "",
    }).encode("utf-8"))
    async with websockets.connect(_WS_URL, max_size=10 * 1024 * 1024) as ws:
        await ws.send(auth)
        on_log(f"danmu connected room={room_id}")

        async def heartbeat():
            while True:
                try:
                    await ws.send(_pack(2))
                except Exception:
                    return
                await asyncio.sleep(30)

        hb = asyncio.ensure_future(heartbeat())
        try:
            async for raw in ws:
                if isinstance(raw, str):
                    continue
                def on_json(msg):
                    if msg.get("cmd") == "DANMU_MSG":
                        info = msg.get("info") or []
                        try:
                            text = info[1]
                            user = (info[2] or [None, ""])[1]
                            if text:
                                on_danmu(user, text)
                        except Exception:
                            pass
                _parse_packets(raw, on_json)
        finally:
            hb.cancel()


class DanmuClient:
    def __init__(self, room_id):
        self.room_id = int(room_id)
        self.running = False
        self._thread = None
        self._loop = None

    def start(self, on_danmu, on_log=lambda m: None):
        self.running = True

        def _thread_main():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            while self.running:
                try:
                    self._loop.run_until_complete(_run(self.room_id, on_danmu, on_log))
                except Exception as e:
                    on_log(f"danmu error: {e}; reconnecting in 10s")
                    for _ in range(100):
                        if not self.running:
                            break
                        self._loop.run_until_complete(asyncio.sleep(0.1))
            try:
                self._loop.close()
            except Exception:
                pass

        self._thread = threading.Thread(target=_thread_main, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False


def start_danmu(room_id, on_danmu, on_log=lambda m: None):
    """進程級單例：重複調用會先停掉舊連接。"""
    global _client
    with _client_lock:
        if _client is not None:
            _client.stop()
        # 依賴檢查提前到這裡，給出可讀錯誤
        try:
            import websockets  # noqa: F401
            import brotli  # noqa: F401
        except ImportError as e:
            raise RuntimeError(f"缺少依賴 {e.name}，請執行: py -3.13 -m pip install websockets brotli")
        _client = DanmuClient(room_id)
        _client.start(on_danmu, on_log)
        return _client


def stop_danmu():
    global _client
    with _client_lock:
        if _client is not None:
            _client.stop()
            _client = None
            return True
        return False


def danmu_status():
    with _client_lock:
        if _client is None:
            return {"running": False}
        return {"running": _client.running, "room_id": _client.room_id}
