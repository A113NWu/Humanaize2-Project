"""Humanaize2 系統托盤圖標（pywin32 實現，無額外第三方依賴）。

用法：
    tray = TrayIcon(on_open=dashboard_url, on_exit=cleanup_fn)
    tray.run()          # 阻塞：消息循環（必須在創建圖標的線程上運行，通常是主線程）

菜單：打開管理面板 / 退出。左鍵雙擊 = 打開管理面板。
"""

import threading
import webbrowser

import win32api
import win32con
import win32gui

_WM_TRAYICON = win32con.WM_USER + 20
_ID_OPEN = 1023
_ID_EXIT = 1024
_NIF_GUID = 0x00000020


class TrayIcon:
    def __init__(self, tooltip="Humanaize2", dashboard_url=None, on_exit=None):
        self._tooltip = tooltip
        self._dashboard_url = dashboard_url
        self._on_exit = on_exit
        self._hwnd = None
        self._ready = threading.Event()

    # ---------------- 內部 ----------------

    def _load_icon(self):
        """優先加載 exe 自身圖標（PyInstaller 打包後資源 ID 1），失敗回退系統默認。"""
        try:
            hinst = win32api.GetModuleHandle(None)
            return win32gui.LoadImage(
                hinst, 1, win32con.IMAGE_ICON, 0, 0,
                win32con.LR_DEFAULTSIZE,
            )
        except Exception:
            return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    def _notify(self, message):
        nid = (
            self._hwnd,
            1,  # uID
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            _WM_TRAYICON,
            self._hicon,
            self._tooltip[:63],
        )
        win32gui.Shell_NotifyIcon(message, nid)

    def _show_menu(self):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, _ID_OPEN, "打開管理面板")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, _ID_EXIT, "退出 Humanaize2")
        win32gui.SetMenuDefaultItem(menu, _ID_OPEN, False)
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        win32gui.TrackPopupMenu(
            menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self._hwnd, None
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)

    def _open_dashboard(self):
        if self._dashboard_url:
            webbrowser.open(self._dashboard_url)

    def _shutdown(self):
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self._hwnd, 1))
        except Exception:
            pass
        if self._on_exit:
            try:
                self._on_exit()
            except Exception:
                pass
        win32gui.PostQuitMessage(0)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == _WM_TRAYICON:
            if lparam == win32con.WM_LBUTTONDBLCLK:
                self._open_dashboard()
            elif lparam == win32con.WM_RBUTTONUP:
                self._show_menu()
        elif msg == win32con.WM_COMMAND:
            if wparam == _ID_OPEN:
                self._open_dashboard()
            elif wparam == _ID_EXIT:
                self._shutdown()
        elif msg == win32con.WM_DESTROY:
            self._shutdown()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    # ---------------- 公開 ----------------

    def run(self):
        """阻塞運行消息循環（必須在主線程調用）。"""
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "Humanaize2Tray"
        wc.hInstance = win32api.GetModuleHandle(None)
        atom = win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(
            atom, "Humanaize2Tray", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
        )
        self._hicon = self._load_icon()
        self._notify(win32gui.NIM_ADD)
        self._ready.set()
        win32gui.PumpMessages()

    def stop(self):
        """從其他線程請求退出。"""
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
