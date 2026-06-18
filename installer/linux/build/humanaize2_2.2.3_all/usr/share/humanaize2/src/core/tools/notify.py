"""
Humanaize v2.0 - 桌面通知模块

支持 Linux (notify-send)、Windows、macOS 的桌面通知
"""

import subprocess
import sys
import os
from typing import Optional


class Notifier:
    """桌面通知管理器"""
    
    def __init__(self, app_name: str = "Humanaize"):
        self.app_name = app_name
        self.enabled = True
        self._check_availability()
    
    def _check_availability(self):
        """检查通知系统是否可用"""
        if sys.platform == "linux" or os.name == "posix":
            # 检查 notify-send 是否存在
            try:
                subprocess.run(["which", "notify-send"], check=True, capture_output=True)
                self._method = "notify-send"
            except subprocess.CalledProcessError:
                self._method = None
                self.enabled = False
        elif sys.platform == "win32" or os.name == "nt":
            # Windows 使用 PowerShell 或 win10toast
            self._method = "windows"
        elif sys.platform == "darwin":
            # macOS 使用 osascript
            self._method = "osascript"
        else:
            self._method = None
            self.enabled = False
    
    def send(self, title: str, message: str, urgency: str = "normal", timeout: int = 5000) -> bool:
        """
        发送桌面通知
        
        Args:
            title: 通知标题
            message: 通知内容
            urgency: 紧急程度 (low, normal, critical)
            timeout: 显示时间（毫秒）
        
        Returns:
            bool: 是否成功发送
        """
        if not self.enabled or not self._method:
            return False
        
        try:
            if self._method == "notify-send":
                # Linux notify-send
                cmd = [
                    "notify-send",
                    "-a", self.app_name,
                    "-u", urgency,
                    "-t", str(timeout),
                    title,
                    message
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                return True
            
            elif self._method == "osascript":
                # macOS osascript
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                return True
            
            elif self._method == "windows":
                # Windows PowerShell
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $template = @"
                <toast>
                    <visual>
                        <binding template="ToastText02">
                            <text id="1">{title}</text>
                            <text id="2">{message}</text>
                        </binding>
                    </visual>
                </toast>
                "@
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{self.app_name}").Show($toast)
                '''
                subprocess.run(["powershell", "-Command", ps_script], check=True, capture_output=True)
                return True
            
        except Exception as e:
            print(f"[Notify] Error: {e}")
            return False
        
        return False
    
    def notify_update(self, new_version: str, current_version: str) -> bool:
        """通知用户有新版本更新"""
        title = "Humanaize 更新可用"
        message = f"发现新版本 {new_version}（当前版本 {current_version}）\n请运行 'humanaize2 update' 进行更新"
        return self.send(title, message, urgency="normal", timeout=10000)
    
    def notify_ai_decision(self, decision: str, reason: str = "") -> bool:
        """通知AI决定是否回复的结果"""
        title = "AI 决策结果"
        if decision.lower() == "yes" or decision.lower() == "是":
            message = f"AI 决定回复用户\n原因: {reason}"
        else:
            message = f"AI 决定暂不回复\n原因: {reason}"
        return self.send(title, message, urgency="low", timeout=3000)
    
    def notify_ai_response(self, response_preview: str = "") -> bool:
        """通知AI已回复"""
        title = "AI 已回复"
        # 截取前50个字符作为预览
        preview = response_preview[:50] + "..." if len(response_preview) > 50 else response_preview
        message = f"AI 已完成回复\n{preview}"
        return self.send(title, message, urgency="normal", timeout=5000)
    
    def notify_error(self, error_message: str) -> bool:
        """通知错误"""
        title = "Humanaize 错误"
        return self.send(title, error_message, urgency="critical", timeout=10000)
    
    def notify_info(self, title: str, message: str) -> bool:
        """发送普通信息通知"""
        return self.send(title, message, urgency="normal", timeout=5000)


# 全局通知器实例
_notifier: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """获取全局通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


def notify_update(new_version: str, current_version: str) -> bool:
    """通知更新"""
    return get_notifier().notify_update(new_version, current_version)


def notify_ai_decision(decision: str, reason: str = "") -> bool:
    """通知AI决策"""
    return get_notifier().notify_ai_decision(decision, reason)


def notify_ai_response(response_preview: str = "") -> bool:
    """通知AI回复"""
    return get_notifier().notify_ai_response(response_preview)


def notify_error(error_message: str) -> bool:
    """通知错误"""
    return get_notifier().notify_error(error_message)


def notify_info(title: str, message: str) -> bool:
    """发送普通通知"""
    return get_notifier().notify_info(title, message)