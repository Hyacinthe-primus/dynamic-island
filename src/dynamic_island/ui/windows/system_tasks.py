"""Island system integration: periodic polling, quick settings, media, taskbar and fullscreen."""
import ctypes
import threading
import time
import webbrowser
from ctypes import wintypes

import psutil
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from dynamic_island.core.config.settings import settings
from dynamic_island.core.localization import translate as tr
from dynamic_island.services import system
from dynamic_island.ui.components.painting import accent_from
from dynamic_island.ui.themes import G, T

user32 = ctypes.windll.user32


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class IslandSystem:
    """Mixin for Island: state read from and actions sent to Windows."""

    def poll_fast(self):
        v, m = self.audio.volume(), self.audio.muted()
        if (abs(v - self.vol) > 0.004 or m != self.muted) and self.drag is None:
            if not (self.is_open and self.tab == "controls"):
                self.show_alert("volume", tr("island.volume.muted") if m else tr("island.volume.title"),
                                "", T.text, G["mute"] if m else G["vol"], bar=0 if m else v)
        self.vol, self.muted = v, m
        caps, num = system.caps_lock(), system.num_lock()
        if caps != self.caps:
            self.show_alert("key", tr("island.keyboard.caps_on" if caps else "island.keyboard.caps_off"),
                            tr("island.keyboard.subtitle"), T.success if caps else T.text, G["keyboard"])
        if num != self.num:
            self.show_alert("key", tr("island.keyboard.num_on" if num else "island.keyboard.num_off"),
                            tr("island.keyboard.subtitle"), T.success if num else T.text, G["keyboard"])
        self.caps, self.num = caps, num

    def check_reminders(self):
        self.agenda.check_reminders()
        self.tasks.check_reminders()

    def update_stats(self):
        self.night = system.night_light_on()
        self.cam_allowed = system.camera_allowed()
        cam = system.camera_in_use()
        if cam and not self.cam_busy:
            self.show_alert("cam", tr("island.camera.active"), tr("island.camera.active_hint"),
                            T.success, G["cam"])
        self.cam_busy = cam
        self.mic_busy = system.mic_in_use()
        dev = self.audio.default_id()
        if dev != self.out_id:
            self.out_id = dev
            self.audio.refresh()
            self.show_alert("output", tr("island.audio.output"), self.audio.device_name, T.accent,
                            G["headphone"] if self.headphones() else G["speaker"])
        b = psutil.sensors_battery()
        if b is None:
            self.battery = None
            return
        pct = int(round(b.percent))
        self.battery = (pct, b.power_plugged)
        if self.plugged is not None and b.power_plugged != self.plugged:
            if b.power_plugged:
                self.show_alert("charge", tr("island.battery.charging"),
                                tr("island.battery.charging_value", percent=pct), T.success, G["charging"])
            else:
                self.show_alert("battery", tr("island.battery.on_battery"),
                                tr("island.battery.remaining", percent=pct), T.text, G["battery"])
        self.plugged = b.power_plugged
        if not b.power_plugged and pct <= 20 and not self.low_warned:
            self.low_warned = True
            self.show_alert("battery", tr("island.battery.low"),
                            tr("island.battery.remaining", percent=pct), T.critical, G["battery"])
        if b.power_plugged or pct > 25:
            self.low_warned = False

    def headphones(self):
        n = self.audio.device_name.lower()
        return any(k in n for k in ("casque", "headphone", "headset", "écouteurs", "airpods", "buds"))

    def on_radios(self, st):
        self.wifi, self.bt = st.get("wifi"), st.get("bluetooth")

    def on_media(self, info):
        if info is None:
            self.media = None
            self.media_key = None
            return
        key = (info["title"], info["artist"])
        if info["thumb"] is not self.thumb_bytes:
            self.thumb_bytes = info["thumb"]
            self.art = None
            if info["thumb"]:
                img = QImage.fromData(info["thumb"])
                if not img.isNull():
                    side = min(img.width(), img.height())
                    img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
                    self.art = QPixmap.fromImage(img.scaled(160, 160, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                            Qt.TransformationMode.SmoothTransformation))
                    self.accent = accent_from(img)
            if self.art is None:
                self.accent = QColor(T.accent)
        if key != self.media_key:
            if not self.first_media and info["playing"]:
                self.show_alert("media", info["title"], info["artist"] or info["app"], self.accent)
            self.media_key = key
        self.first_media = False
        if self.media and time.time() - self.media.get("local_t", 0) < 1.2:
            info["playing"] = self.media["playing"]
            info["local_t"] = self.media["local_t"]
        self.media = info
        self.media_at = time.time()
        app_key = (info.get("aumid"), info["title"])
        if app_key != self._media_app_key:
            self._media_app_key = app_key
            def find(a=info.get("aumid"), t=info["title"]):
                self.media_exe = system.find_app_window(a, t)[1]
            threading.Thread(target=find, daemon=True).start()

    def media_position(self):
        m = self.media
        pos = m["position"]
        if m["playing"]:
            pos += max(0.0, time.time() - (m["updated_at"] or self.media_at))
        return min(pos, m["duration"]) if m["duration"] > 0 else pos

    def open_media_app(self):
        """Open the application that is playing media (Spotify, browser, player…)."""
        m = self.media
        if not m:
            return
        self.close_island(restore_focus=False)
        if not system.open_media_app(m.get("aumid", ""), m["title"]):
            self.show_alert("media", tr("island.media.app_not_found"), m.get("app") or "",
                            T.critical, G["error"])

    def media_cmd(self, name, arg=None):
        self.worker.command(name, arg)
        if not self.media:
            return
        if name == "play_pause":
            self.media["position"] = self.media_position()
            self.media["updated_at"] = time.time()
            self.media["playing"] = not self.media["playing"]
            self.media["local_t"] = time.time()
        elif name == "seek":
            self.media["position"] = arg
            self.media["updated_at"] = time.time()

    def set_focus(self, on):
        self.timers.set_focus(on)
        if on and not self.dnd.on:
            self.dnd.toggle()
            self._dnd_by_focus = True
        elif not on and self._dnd_by_focus:
            if self.dnd.on:
                self.dnd.toggle()
            self._dnd_by_focus = False
        self.show_alert("focus", tr("island.focus.enabled" if on else "island.focus.disabled"),
                        tr("island.focus.active_hint", minutes=self.timers.pomo_cfg["work"]) if on
                        else tr("island.focus.done"), T.accent, G["focus"])

    def airplane_on(self):
        st = [x for x in (self.wifi, self.bt) if x is not None]
        return bool(st) and not any(st)

    def toggle_radio(self, kind):
        cur = self.wifi if kind == "wifi" else self.bt
        if cur is None:
            return
        if kind == "wifi":
            self.wifi = not cur
        else:
            self.bt = not cur
        self.radio.set_radio(kind, not cur)

    def toggle_airplane(self):
        on = not self.airplane_on()
        self.radio.set_airplane(on)
        if on:
            self.wifi = False if self.wifi is not None else None
            self.bt = False if self.bt is not None else None

    def toggle_night(self):
        target = not self.night
        if system.set_night_light(target):
            self.night = target
            return
        self.show_alert("night", tr("controls.tiles.night_light"),
                        tr("controls.night_settings_hint"), T.caution, G["night"])
        self.open_url("ms-settings:nightlight")

    def toggle_camera(self):
        system.set_camera_allowed(not self.cam_allowed)
        self.cam_allowed = not self.cam_allowed

    def stay_on_screen(self):
        """Keep the island visible above everything, even fullscreen applications."""
        if not self.isVisible():
            self.show()
            system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, self.focus_field is None)
        system.keep_topmost(self.hwnd)

    @property
    def taskbar_hidden(self):
        return settings.get("hide_taskbar", True)

    def apply_taskbar(self):
        if self.taskbar_hidden:
            if "taskbar_prev_autohide" not in settings:
                settings.set("taskbar_prev_autohide", system.taskbar_autohide())
            system.set_taskbar_autohide(True)
            system.hide_taskbar()
        else:
            self.restore_taskbar()

    def restore_taskbar(self):
        system.show_taskbar()
        if "taskbar_prev_autohide" in settings:
            system.set_taskbar_autohide(bool(settings.pop("taskbar_prev_autohide")))
            settings.save()

    def set_taskbar_hidden(self, on):
        settings.set("hide_taskbar", on)
        self.apply_taskbar()

    def enforce_taskbar(self):
        """Windows shows the taskbar again on hover, Start click or Explorer restart; hide it again."""
        if self.taskbar_hidden and system.hide_taskbar():
            system.set_taskbar_autohide(True)

    def check_fullscreen(self):
        fs = self.foreground_fullscreen()
        if fs and self.isVisible():
            self.hide()
        elif not fs and not self.isVisible():
            self.show()
            system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, self.focus_field is None)

    def foreground_fullscreen(self):
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == self.hwnd:
            return False
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return False
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom

    def on_clipboard_for_phone(self):
        ph = self.phone
        if not (ph.sync_clip and ph.running):
            return
        t = QApplication.clipboard().text()
        if t and t != getattr(self, "_from_phone", None) and (not ph.outbox or ph.outbox[0]["text"] != t):
            ph.push_text(t, "clip")

    def on_remote(self, action, arg):
        keys = {"play": 0xB3, "next": 0xB0, "prev": 0xB1, "volup": 0xAF, "voldown": 0xAE, "mute": 0xAD,
                "left": 0x25, "right": 0x27, "space": 0x20}
        if action in keys:
            vk = keys[action]
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
        elif action == "open" and arg.lower().startswith(("http://", "https://")):
            webbrowser.open(arg)
