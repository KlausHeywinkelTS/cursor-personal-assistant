"""Desktop-Benachrichtigungen. Der Service ruft nur das Notifier-Interface auf.

Weitere Backends (Discord, E-Mail) lassen sich später als zusätzliche Klassen ergänzen.
Titel und Text werden nie in Skriptcode interpoliert, sondern über Umgebungsvariablen übergeben.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from typing import Protocol

log = logging.getLogger("team_manager.notify")


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> None: ...


class NullNotifier:
    def notify(self, title: str, message: str) -> None:
        return None


class RecordingNotifier:
    """Für Tests."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.sent.append((title, message))


_WINDOWS_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $xml.GetElementsByTagName('text')
$text[0].AppendChild($xml.CreateTextNode($env:TM_TITLE)) | Out-Null
$text[1].AppendChild($xml.CreateTextNode($env:TM_MESSAGE)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""

_MACOS = 'display notification (system attribute "TM_MESSAGE") with title (system attribute "TM_TITLE")'


class SystemNotifier:
    """Windows-Toast, macOS-Mitteilung oder notify-send. Versand in einem Hintergrundthread."""

    def notify(self, title: str, message: str) -> None:
        threading.Thread(target=self._send, args=(title, message), daemon=True).start()

    def _send(self, title: str, message: str) -> None:
        env = {**os.environ, "TM_TITLE": title[:120], "TM_MESSAGE": message[:300]}
        try:
            if sys.platform == "win32":
                cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_TOAST]
            elif sys.platform == "darwin":
                cmd = ["osascript", "-e", _MACOS]
            else:
                cmd = ["notify-send", title[:120], message[:300]]
            subprocess.run(cmd, env=env, timeout=15, capture_output=True, check=False)
        except Exception:  # Benachrichtigung ist nie geschäftskritisch
            log.exception("notification_failed")
