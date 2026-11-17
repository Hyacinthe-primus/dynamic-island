"""Island alerts: transient pill notifications, tray messages and event/reminder handlers."""
import datetime as dt
import os
import time
import winsound

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from dynamic_island.core.localization import format_time, translate as tr
from dynamic_island.core.utilities.formatting import until
from dynamic_island.ui.themes import G, T
from dynamic_island.ui.windows.layout import ALERT_TIME


class IslandAlerts:
    """Mixin for Island: everything that raises or reacts to an alert."""

    ALERT_TABS = {"media": "home", "volume": "controls", "output": "controls", "clip": "clip", "timer": "timers",
                  "alarm": "timers", "pomo": "timers", "event": "agenda", "task": "tasks", "ci_fail": "dev",
                  "build_fail": "dev", "build_ok": "dev", "ci_ok": "dev", "phone": "phone", "phone_notif": "phone",
                  "phone_call": "phone", "phone_file": "files", "files": "files", "download": "files",
                  "launch": "launcher", "wallet": "wallet"}

    def open_alert(self):
        """Click on an alert: dismiss it and open the tab it relates to."""
        a = self.alert or {}
        self.alert_until = 0
        goto = self.ALERT_TABS.get(a.get("kind"))
        if goto:
            self.tab = goto
            self.pinned = True

    def show_alert(self, kind, title, subtitle, color, glyph=None, bar=None, action=None, duration=ALERT_TIME):
        self.alert = {"kind": kind, "title": title, "subtitle": subtitle, "color": QColor(color), "glyph": glyph,
                      "bar": bar, "action": action}
        self.alert_until = time.time() + duration

    def notify(self, title, msg):
        if hasattr(self, "tray") and not self.dnd.on:
            self.tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 6000)

    def on_timer_fired(self, kind, title, sub):
        stop = lambda: winsound.PlaySound(None, 0)
        if kind == "alarm":
            self.show_alert("alarm", title, sub, T.orange, G["alarm"],
                            action=(tr("common.stop"), stop), duration=30)
        elif kind == "pomodoro":
            self.show_alert("pomo", title, sub, T.success, G["focus"], duration=6)
        else:
            self.show_alert("timer", title, sub, T.accent, G["timer"],
                            action=(tr("common.ok"), stop), duration=12)
        self.notify(title, sub)

    def on_event_reminder(self, event):
        sub = until(event["start"] - time.time()).capitalize() + " · " + format_time(
            dt.datetime.fromtimestamp(event["start"])
        )
        action = (tr("common.join"), lambda url=event["meet_url"]: self.open_url(url)) \
            if event.get("meet_url") else None
        self.show_alert("event", event["title"], sub, T.accent,
                        G["video"] if event.get("meet_url") else G["calendar"],
                        action=action, duration=15)
        self.notify(tr("island.notify.event", title=event["title"]), sub)

    def on_task_reminder(self, task):
        self.show_alert("task", task["title"], tr("island.notify.task_reminder"), T.orange, G["tasks"],
                        action=(tr("common.done"), lambda task=task: self.tasks.toggle(task)), duration=12)
        self.notify(tr("island.notify.task", title=task["title"]), tr("island.notify.task"))

    def on_dev_alert(self, kind, title, sub):
        ok = kind.endswith("_ok")
        self.show_alert(kind, title, sub, T.success if ok else T.critical,
                        G["check"] if ok else G["error"], duration=4 if ok else 8)
        if not ok:
            self.notify(title, sub)

    def on_phone_text(self, text):
        self._from_phone = text
        QApplication.clipboard().setText(text)
        self.show_alert("phone", tr("island.phone.received"),
                        tr("island.phone.received_text", text=" ".join(text.split())[:70]),
                        T.accent, G["phone"])

    def on_phone_alert(self, kind, title, sub, data):
        if kind == "phone_call":
            self.show_alert(kind, title, sub or tr("island.phone.incoming_call"), T.success,
                            G["phone"], duration=20,
                            action=(tr("common.link"), lambda: self.tabs["phone"]._open_link()))
        elif kind == "phone_file":
            self.show_alert(kind, title, sub, T.accent, G["phone"], duration=6,
                            action=(tr("common.open"), lambda: self.files.open(data)))
        elif kind == "phone_err":
            self.show_alert(kind, title, sub, T.critical, G["error"], duration=6)
        else:
            self.show_alert(kind, title, sub, T.accent, G["bell"], duration=5)

    def on_files_alert(self, kind, title, path):
        if kind == "download":
            self.show_alert(kind, title, os.path.basename(path), T.success, "\ue896", duration=6,
                            action=(tr("common.open"), lambda path=path: self.files.open(path)))
        else:
            self.show_alert(kind, title, path, T.accent, G["folder"])
