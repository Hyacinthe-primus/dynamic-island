"""Dynamic Island pour Windows — style Windows 11."""
import ctypes
import datetime as dt
import math
import os
import sys
import threading
import time
import webbrowser
import winreg
import winsound
from ctypes import wintypes

import psutil
from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon, QWidget

import system as S
from agenda import Agenda
from clipboard import ClipboardHistory
from devtools import Dev
from infos import Infos
from media import MediaWorker
from hotspot import Hotspot
from network import Networks
from store import Collection, settings
from binance import Binance
from files import Files
from launcher import Launcher
from phone import Phone
from tab_agenda import AgendaTab
from tab_clip import ClipTab
from tab_controls import ControlsTab
from tab_dev import DevTab
from tab_files import FilesTab
from tab_home import HomeTab
from tab_infos import InfosTab
from tab_launcher import LauncherTab
from tab_phone import PhoneTab
from tab_tasks import TasksTab
from tab_timers import TimersTab
from tab_wallet import WalletTab
from tasks import Tasks
from theme import G, R_COMPACT, R_OPEN, T, W, font
from timers import Timers
from ui import CENTER, LEFT, RIGHT, UI, fmt_dur, smooth, spring, until

# ------------------------------------------------------------------ dimensions
COMPACT = (132, 34)
COMPACT_MEDIA = (260, 34)
COMPACT_TIMER = (236, 34)
COMPACT_MEET = (300, 34)
COMPACT_BUILD = (210, 34)
ALERT = (360, 64)
EW = 620
TAB_H = 46
PAD = 10                 # marge pour l'ombre
WIN_W, WIN_H = EW + 420, TAB_H + 380 + 60   # large : place pour le dock des applis à droite de la pilule
TOP_MARGIN = 0
HOVER_DELAY = 0.07
LEAVE_DELAY = 0.30
ALERT_TIME = 2.8
HOTKEY_ID = 1
HOTKEY_LAUNCH = 2

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DynamicIsland"
user32 = ctypes.windll.user32
DOCK_MAX = 9          # icônes affichées dans le dock (au-delà : « +N »)
DOCK_CELL = 30
MENU_QSS = ("QMenu{background:#000;color:#fff;border:1px solid #333;padding:4px;border-radius:8px}"
            "QMenu::item{padding:6px 22px 6px 14px;border-radius:4px}"
            "QMenu::item:selected{background:#262626}QMenu::item:disabled{color:#8a8a8a}"
            "QMenu::separator{height:1px;background:#2a2a2a;margin:4px 8px}")
COMPACT_MODES = ("compact", "cmedia", "ctimer", "cmeet", "cbuild")


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def accent_from(img: QImage) -> QColor:
    small = img.scaled(10, 10, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    best, score = None, -1
    for x in range(small.width()):
        for y in range(small.height()):
            c = QColor(small.pixel(x, y))
            s = c.hsvSaturationF() * c.valueF()
            if s > score:
                best, score = c, s
    if best is None or score < 0.15:
        return QColor(T.accent)
    return QColor.fromHsv(best.hsvHue(), min(255, max(140, best.hsvSaturation())), max(200, best.value()))


def make_tray_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(32, 32, 32))
    p.setPen(QPen(QColor(255, 255, 255, 140), 2))
    p.drawRoundedRect(QRectF(4, 20, 56, 24), 7, 7)
    p.setBrush(QColor(T.accent))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(48, 32), 5, 5)
    p.end()
    return QIcon(pm)


# ================================================================== île
class Island(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(WIN_W, WIN_H)
        self.place()
        self.hwnd = int(self.winId())
        S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, True)
        self.click_through = None
        self.ui = UI(self)

        # animation
        self.w, self.h = COMPACT
        self.vw = self.vh = 0.0
        self.mode = self.prev_mode = "compact"
        self.mode_t = 0.0
        self.slide_dir = 0
        self.moving = False
        self._cc = {}
        self.dock_alpha = 0.0
        self.dock_hover = None
        self._dock_sig = None
        self.last_tick = time.time()
        self.t0 = time.time()

        # interaction
        self.hovered = self.pinned = self.hover_block = False
        self.enter_at = self.leave_at = None
        self.mouse = QPointF(-1, -1)
        self.hits, self.sliders, self.scroll_regions = [], [], []
        self.scrolls, self.scroll_content = {}, {}
        self.clip_rect = None
        self._reg = False
        self.drag = None
        self.fields, self.field_handlers = {}, {}
        self.focus_field = None
        self.prev_fg = None

        # alertes
        self.alert = None
        self.alert_until = 0.0

        # média
        self.media = None
        self.media_at = 0.0
        self.media_key = None
        self.first_media = True
        self.art = None
        self.thumb_bytes = None
        self.accent = QColor(T.accent)
        self.media_exe = None      # exécutable de l'appli qui joue (pour son icône)
        self._media_app_key = None

        # système
        self.audio = S.Audio()
        self.bright = S.Brightness()
        self.dnd = S.DoNotDisturb()
        self.radio = S.RadioWorker()
        self.radio.updated.connect(self.on_radios)
        self.radio.start()
        self.wifi = self.bt = None
        self.night = S.night_light_on()
        self.night_ok = S.night_light_supported()
        self.cam_allowed = S.camera_allowed()
        self.cam_busy = self.mic_busy = False
        self.caps, self.num = S.caps_lock(), S.num_lock()
        self.vol, self.muted = self.audio.volume(), self.audio.muted()
        self.out_id = self.audio.default_id()
        psutil.cpu_percent(None)
        self.battery = None
        self.plugged = None
        self.low_warned = False
        self._dnd_by_focus = False

        # services
        self.clip = ClipboardHistory(QApplication.clipboard())
        self.agenda = Agenda()
        self.timers = Timers()
        self.tasks = Tasks()
        self.infos = Infos()
        self.dev = Dev()
        self.files = Files()
        self.launcher = Launcher()
        self.phone = Phone(self.files)
        self.wallet = Binance()
        self.net = Networks()
        self.hotspot = Hotspot()
        self.hotspot.alert.connect(lambda t, s_, ok: self.show_alert("hotspot", t, s_, T.success if ok else T.critical,
                                                                     chr(0xE88A), duration=5))
        self.net.alert.connect(lambda t, s_, ok: self.show_alert("net", t, s_, T.success if ok else T.critical,
                                                                 G["wifi"] if "Wi-Fi" in t else G["bt"], duration=4))
        QTimer.singleShot(4000, lambda: (self.net.scan_wifi(active=False), self.net.refresh_bt()))
        self.files.alert.connect(self.on_files_alert)
        self.launcher.output.connect(lambda t, s_: self.show_alert("launch", t, s_, T.accent, G["terminal"]))
        self.phone.alert.connect(self.on_phone_alert)
        self.phone.text_received.connect(self.on_phone_text)
        self.phone.remote.connect(self.on_remote)
        QApplication.clipboard().dataChanged.connect(self.on_clipboard_for_phone)
        self.draggables, self._press = [], None
        self.drop_hover = self.drag_out = False
        self.setAcceptDrops(True)
        self.agenda.reminder.connect(self.on_event_reminder)
        self.tasks.reminder.connect(self.on_task_reminder)
        self.timers.fired.connect(self.on_timer_fired)
        self.dev.alert.connect(self.on_dev_alert)

        # onglets
        self.tabs = {}
        for cls in (HomeTab, AgendaTab, TimersTab, TasksTab, LauncherTab, FilesTab, PhoneTab, InfosTab, WalletTab,
                    DevTab, ControlsTab, ClipTab):
            t = cls(self)
            self.tabs[t.key] = t
        self.tab_keys = list(self.tabs)
        self.tab = "home"
        self.tab_x = 0.0

        self.update_stats()

        self.anim = QTimer(self)
        self.anim.setTimerType(Qt.TimerType.PreciseTimer)
        self.anim.timeout.connect(self.tick)
        self.anim.start(8)
        self._fast_t = self._mid_t = 0.0
        QTimer(self, interval=1500, timeout=self.update_stats).start()
        QTimer(self, interval=2000, timeout=self.stay_on_screen).start()
        QTimer(self, interval=400, timeout=self.enforce_taskbar).start()
        QTimer(self, interval=1000, timeout=self.refresh_visible).start()
        QTimer(self, interval=5000, timeout=Collection.sync_all).start()
        QTimer(self, interval=15000, timeout=self.check_reminders).start()

        # préchauffe les polices de chaque onglet (évite un à-coup au premier affichage)
        QTimer.singleShot(1500, self.warmup)

        self.worker = MediaWorker()
        self.worker.updated.connect(self.on_media)
        self.worker.start()
        user32.RegisterHotKey(self.hwnd, HOTKEY_ID, 0x0002 | 0x0001 | 0x4000, 0x56)  # Ctrl+Alt+V
        user32.RegisterHotKey(self.hwnd, HOTKEY_LAUNCH, 0x0002 | 0x0001 | 0x4000, 0x20)  # Ctrl+Alt+Espace

    # ------------------------------------------------------------ géométrie
    def place(self):
        geo = QApplication.primaryScreen().geometry()
        self.move(geo.x() + (geo.width() - WIN_W) // 2, geo.y() + TOP_MARGIN)

    def pill_rect(self):
        return QRectF((WIN_W - self.w) / 2, PAD, self.w, self.h)

    @property
    def is_open(self):
        return (self.hovered or self.pinned or self.focus_field is not None or self.drag is not None
                or self.drop_hover)

    def compact_mode(self):
        now = time.time()
        if self.timers.active():
            return COMPACT_TIMER, "ctimer"
        if now - getattr(self, "_nxt_t", 0) > 1:
            self._nxt_t, self._nxt = now, self.agenda.next_timed()
        nxt = self._nxt
        if nxt and nxt["start"] - now <= 15 * 60 and now < nxt["start"] + 5 * 60:
            return COMPACT_MEET, "cmeet"
        if self.media:
            return COMPACT_MEDIA, "cmedia"
        if self.dev.build and self.dev.build.get("running"):
            return COMPACT_BUILD, "cbuild"
        return COMPACT, "compact"

    def target(self):
        if self.alert and time.time() < self.alert_until and not self.is_open:
            w = ALERT[0] + (90 if self.alert.get("action") else 0)
            return (w, ALERT[1]), "alert"
        if self.is_open:
            return (EW, TAB_H + self.tabs[self.tab].height()), "tab:" + self.tab
        return self.compact_mode()

    # ------------------------------------------------------------ boucle
    def tick(self):
        now = time.time()
        dt_ = min(0.05, max(0.001, now - self.last_tick))
        self.last_tick = now
        if T.check():
            self.update()

        self.mouse = QPointF(self.mapFromGlobal(QCursor.pos()))
        m = 10 if self.is_open else 6
        inside = self.isVisible() and self.pill_rect().adjusted(-m, -m - PAD, m, m + 4).contains(self.mouse)

        dock_r, dock_items = self.dock_layout()
        in_dock = dock_r is not None and self.dock_alpha > 0.5 and dock_r.adjusted(-4, -PAD, 4, 4).contains(self.mouse)
        hov = None
        if in_dock:
            for i, (rr, _g) in enumerate(dock_items):
                if rr.contains(self.mouse):
                    hov = i
        dock_changed = hov != self.dock_hover
        self.dock_hover = hov
        want = 1.0 if (self.dock_enabled and not self.is_open and self.launcher.running) else 0.0
        self.dock_alpha += (want - self.dock_alpha) * min(1.0, dt_ * 12)
        if abs(want - self.dock_alpha) < 0.01:
            self.dock_alpha = want
        sig = tuple((g["key"], len(g["windows"])) for g in self.launcher.running[:DOCK_MAX + 1])
        sig += (user32.GetForegroundWindow(),)
        if sig != self._dock_sig:
            self._dock_sig = sig
            dock_changed = True
        through = not (inside or in_dock) and self.drag is None and self.focus_field is None
        if through != self.click_through:
            S.set_exstyle(self.hwnd, S.WS_EX_TRANSPARENT, through)
            self.click_through = through

        if inside:
            self.leave_at = None
            if not self.hovered and not self.hover_block:
                if self.enter_at is None:
                    self.enter_at = now
                elif now - self.enter_at >= HOVER_DELAY:
                    self.hovered = True
        else:
            self.enter_at = None
            self.hover_block = False
            if self.hovered:
                if self.leave_at is None:
                    self.leave_at = now
                elif now - self.leave_at >= LEAVE_DELAY:
                    self.hovered = False

        if (self.pinned or self.focus_field) and not inside and user32.GetAsyncKeyState(0x01) & 0x8000:
            self.close_island(restore_focus=False)

        (tw, th), mode = self.target()
        if mode != self.mode:
            if mode.startswith("tab:") and self.mode.startswith("tab:"):
                a, b = self.tab_keys.index(self.mode[4:]), self.tab_keys.index(mode[4:])
                self.slide_dir = 1 if b > a else -1
            else:
                self.slide_dir = 0
            self.prev_mode, self.mode, self.mode_t = self.mode, mode, now
            if mode.startswith("tab:"):
                t = self.tabs[mode[4:]]
                if hasattr(t, "on_open"):
                    t.on_open()
        self.w, self.vw = spring(self.w, self.vw, tw, 430, dt_)
        self.h, self.vh = spring(self.h, self.vh, th, 520, dt_)
        moving = abs(self.vw) > 2 or abs(self.vh) > 2 or abs(tw - self.w) > 0.3 or abs(th - self.h) > 0.3
        if not moving:
            self.w, self.h, self.vw, self.vh = tw, th, 0.0, 0.0
        self.moving = moving

        idx = self.tab_keys.index(self.tab)
        self.tab_x += (idx - self.tab_x) * min(1.0, dt_ * 18)
        for k, (cur, tgt) in list(self.scrolls.items()):
            if abs(tgt - cur) > 0.3:
                self.scrolls[k] = (cur + (tgt - cur) * min(1.0, dt_ * 16), tgt)
            elif cur != tgt:
                self.scrolls[k] = (tgt, tgt)

        if now - self._fast_t > 0.12:
            self._fast_t = now
            self.poll_fast()
        if now - self._mid_t > 0.25:
            self._mid_t = now
            self.timers.tick()

        fading = now - self.mode_t < 0.35
        scrolling = any(abs(c - t) > 0.3 for c, t in self.scrolls.values())
        animating = (moving or fading or abs(idx - self.tab_x) > 0.002 or scrolling
                     or 0.0 < self.dock_alpha < 1.0)
        live = bool(self.media and self.media["playing"]) or self.timers.active() is not None or bool(self.focus_field)
        self.anim.setInterval(7 if animating else (16 if (live or inside) else 40))
        # on ne redessine que si quelque chose change (souris, animation, contenu vivant)
        moved = self.mouse != getattr(self, "_last_mouse", None)
        self._last_mouse = QPointF(self.mouse)
        since = now - getattr(self, "_last_paint", 0)
        need = (animating or self.drag or (inside and moved) or dock_changed or int(now) != int(now - dt_)
                or (live and since > (0.033 if self.media and self.media["playing"] else 0.25))
                or (self.is_open and since > 0.5))
        if need:
            self._last_paint = now
            # zone à rafraîchir : île actuelle + précédente (+ ombre), pas toute la fenêtre
            r = self.pill_rect().adjusted(-14, -PAD, 14, 14).toAlignedRect()
            if dock_r is not None or self.dock_alpha > 0:  # le dock et son étiquette de survol
                r = r.united(QRectF(self.pill_rect().right(), 0, WIN_W - self.pill_rect().right(), 100).toAlignedRect())
            prev = getattr(self, "_last_dirty", r)
            self._last_dirty = r
            self.update(r.united(prev))

    def poll_fast(self):
        v, m = self.audio.volume(), self.audio.muted()
        if (abs(v - self.vol) > 0.004 or m != self.muted) and self.drag is None:
            if not (self.is_open and self.tab == "controls"):
                self.show_alert("volume", "Son coupé" if m else "Volume", "", T.text, G["mute"] if m else G["vol"],
                                bar=0 if m else v)
        self.vol, self.muted = v, m
        caps, num = S.caps_lock(), S.num_lock()
        if caps != self.caps:
            self.show_alert("key", "Verr. Maj " + ("activé" if caps else "désactivé"), "Clavier",
                            T.success if caps else T.text, G["keyboard"])
        if num != self.num:
            self.show_alert("key", "Verr. Num " + ("activé" if num else "désactivé"), "Clavier",
                            T.success if num else T.text, G["keyboard"])
        self.caps, self.num = caps, num

    def refresh_visible(self):
        self.dev.visible = self.is_open and self.tab == "dev"
        self.launcher.running_visible = (self.is_open and self.tab == "launcher"
                                         and self.tabs["launcher"].view == "running")
        vis = self.is_open and self.tab == "wallet"
        if vis and not self.wallet.visible:
            self.wallet.refresh()
        self.wallet.visible = vis
        if self.is_open and self.tab == "controls" and self.drag is None:
            self._ctl_n = getattr(self, "_ctl_n", 0) + 1
            self.tabs["controls"].refresh(brightness=self._ctl_n % 5 == 0)

    def check_reminders(self):
        self.agenda.check_reminders()
        self.tasks.check_reminders()

    # ------------------------------------------------------------ données système
    def update_stats(self):
        self.night = S.night_light_on()
        self.cam_allowed = S.camera_allowed()
        cam = S.camera_in_use()
        if cam and not self.cam_busy:
            self.show_alert("cam", "Caméra active", "Une application utilise la webcam", T.success, G["cam"])
        self.cam_busy = cam
        self.mic_busy = S.mic_in_use()
        dev = self.audio.default_id()
        if dev != self.out_id:
            self.out_id = dev
            self.audio.refresh()
            self.show_alert("output", "Sortie audio", self.audio.device_name, T.accent,
                            G["headphone"] if self.headphones() else G["speaker"])
        b = psutil.sensors_battery()
        if b is None:
            self.battery = None
            return
        pct = int(round(b.percent))
        self.battery = (pct, b.power_plugged)
        if self.plugged is not None and b.power_plugged != self.plugged:
            if b.power_plugged:
                self.show_alert("charge", "En charge", f"Batterie à {pct} %", T.success, G["charging"])
            else:
                self.show_alert("battery", "Sur batterie", f"{pct} % restants", T.text, G["battery"])
        self.plugged = b.power_plugged
        if not b.power_plugged and pct <= 20 and not self.low_warned:
            self.low_warned = True
            self.show_alert("battery", "Batterie faible", f"{pct} % restants", T.critical, G["battery"])
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
                self.media_exe = S.find_app_window(a, t)[1]
            threading.Thread(target=find, daemon=True).start()

    def media_position(self):
        m = self.media
        pos = m["position"]
        if m["playing"]:
            pos += max(0.0, time.time() - (m["updated_at"] or self.media_at))
        return min(pos, m["duration"]) if m["duration"] > 0 else pos

    def open_media_app(self):
        """Affiche l'application qui joue le média (Spotify, navigateur, lecteur…)."""
        m = self.media
        if not m:
            return
        self.close_island(restore_focus=False)
        if not S.open_media_app(m.get("aumid", ""), m["title"]):
            self.show_alert("media", "Application introuvable", m.get("app") or "", T.critical, G["error"])

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

    # ------------------------------------------------------------ notifications
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
            self.show_alert("alarm", title, sub, T.orange, G["alarm"], action=("Arrêter", stop), duration=30)
        elif kind == "pomodoro":
            self.show_alert("pomo", title, sub, T.success, G["focus"], duration=6)
        else:
            self.show_alert("timer", title, sub, T.accent, G["timer"], action=("OK", stop), duration=12)
        self.notify(title, sub)

    def on_event_reminder(self, o):
        sub = until(o["start"] - time.time()).capitalize() + " · " + dt.datetime.fromtimestamp(o["start"]).strftime("%H:%M")
        action = ("Rejoindre", lambda u=o["meet_url"]: self.open_url(u)) if o.get("meet_url") else None
        self.show_alert("event", o["title"], sub, T.accent, G["video"] if o.get("meet_url") else G["calendar"],
                        action=action, duration=15)
        self.notify("Rappel : " + o["title"], sub)

    def on_task_reminder(self, t):
        self.show_alert("task", t["title"], "Rappel de tâche", T.orange, G["tasks"],
                        action=("Fait", lambda t=t: self.tasks.toggle(t)), duration=12)
        self.notify("Tâche : " + t["title"], "Rappel")

    def on_dev_alert(self, kind, title, sub):
        ok = kind.endswith("_ok")
        self.show_alert(kind, title, sub, T.success if ok else T.critical,
                        G["check"] if ok else G["error"], duration=4 if ok else 8)
        if not ok:
            self.notify(title, sub)

    # ------------------------------------------------------------ actions générales
    def set_tab(self, tab):
        if tab != self.tab and self.focus_field:
            self.unfocus(restore=False)
        self.tab = tab

    def open_url(self, url):
        if url:
            webbrowser.open(url)
            self.close_island(restore_focus=False)

    def copy_text(self, text):
        QApplication.clipboard().setText(text)
        self.show_alert("clip", "Copié", text.split("\n")[0][:60], T.accent, G["copy"], duration=1.4)

    def copy_item(self, item):
        if self.clip.copy(item):
            self.show_alert("clip", "Copié", (item.get("text") or "").split("\n")[0][:60], T.accent, G["copy"],
                            duration=1.4)

    def paste_item(self, item):
        target = self.prev_fg if self.focus_field else user32.GetForegroundWindow()
        if not target or target == self.hwnd:
            target = self.prev_fg
        if not self.clip.copy(item):
            return
        self.close_island(restore_focus=False)
        if target:
            S.force_foreground(target)
        QTimer.singleShot(120, S.send_ctrl_v)
        self.show_alert("clip", "Collé", (item.get("text") or "").split("\n")[0][:60], T.success, G["clip"],
                        duration=1.4)

    def close_island(self, restore_focus=True):
        self.pinned = self.hovered = False
        self.hover_block = True
        self.unfocus(restore=restore_focus)
        if hasattr(self, "pin_action"):
            self.pin_action.setChecked(False)

    def open_clipboard(self):
        self.tab = "clip"
        self.pinned = True
        self.fields["clip_search"] = ""
        self.scrolls.pop("clip", None)
        self.focus("clip_search")

    def set_focus(self, on):
        self.timers.set_focus(on)
        if on and not self.dnd.on:
            self.dnd.toggle()
            self._dnd_by_focus = True
        elif not on and self._dnd_by_focus:
            if self.dnd.on:
                self.dnd.toggle()
            self._dnd_by_focus = False
        self.show_alert("focus", "Mode concentration " + ("activé" if on else "terminé"),
                        f"Pomodoro de {self.timers.pomo_cfg['work']} min · Ne pas déranger" if on else "Bon travail !",
                        T.accent, G["focus"])

    # --- système
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
        S.set_night_light(not self.night)
        self.night = not self.night

    def toggle_camera(self):
        S.set_camera_allowed(not self.cam_allowed)
        self.cam_allowed = not self.cam_allowed

    # --- saisie de texte
    def focus(self, name):
        if self.focus_field is None:
            fg = user32.GetForegroundWindow()
            if fg and fg != self.hwnd:
                self.prev_fg = fg
            S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, False)
            S.force_foreground(self.hwnd)
            self.activateWindow()
            self.setFocus()
        self.focus_field = name

    def unfocus(self, restore=True):
        if self.focus_field is None:
            return
        self.focus_field = None
        S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, True)
        if restore and self.prev_fg:
            S.force_foreground(self.prev_fg)

    # --- île permanente + barre des tâches masquée
    def stay_on_screen(self):
        """L'île reste toujours affichée, au-dessus de tout (même des applis en plein écran)."""
        if not self.isVisible():
            self.show()
            S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, self.focus_field is None)
        S.keep_topmost(self.hwnd)

    @property
    def taskbar_hidden(self):
        return settings.get("hide_taskbar", True)

    def apply_taskbar(self):
        if self.taskbar_hidden:
            if "taskbar_prev_autohide" not in settings:
                settings.set("taskbar_prev_autohide", S.taskbar_autohide())
            S.set_taskbar_autohide(True)
            S.hide_taskbar()
        else:
            self.restore_taskbar()

    def restore_taskbar(self):
        S.show_taskbar()
        if "taskbar_prev_autohide" in settings:
            S.set_taskbar_autohide(bool(settings.pop("taskbar_prev_autohide")))
            settings.save()

    def set_taskbar_hidden(self, on):
        settings.set("hide_taskbar", on)
        self.apply_taskbar()

    def enforce_taskbar(self):
        """Windows réaffiche la barre au survol, au clic sur Démarrer, après un redémarrage d'Explorer… on la recache."""
        if self.taskbar_hidden and S.hide_taskbar():
            S.set_taskbar_autohide(True)

    def check_fullscreen(self):
        fs = self.foreground_fullscreen()
        if fs and self.isVisible():
            self.hide()
        elif not fs and not self.isVisible():
            self.show()
            S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, self.focus_field is None)

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

    # ------------------------------------------------------------ événements
    def nativeEvent(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                if self.is_open and self.tab == "clip":
                    self.close_island()
                else:
                    self.open_clipboard()
                return True, 0
            if msg.message == 0x0312 and msg.wParam == HOTKEY_LAUNCH:
                if self.is_open and self.tab == "launcher":
                    self.close_island()
                else:
                    self.tab = "launcher"
                    self.pinned = True
                    self.fields["launch_search"] = ""
                    self.focus("launch_search")
                return True, 0
        except Exception:
            pass
        return False, 0

    def changeEvent(self, e):
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and self.focus_field:
            self.focus_field = None
            S.set_exstyle(self.hwnd, S.WS_EX_NOACTIVATE, True)
        super().changeEvent(e)

    def mousePressEvent(self, e):
        pos = QPointF(e.position())
        dock_r, dock_items = self.dock_layout()
        if dock_r is not None and self.dock_alpha > 0.5 and dock_r.contains(pos):
            for rr, g in dock_items:
                if rr.contains(pos):
                    if g is None:  # « +N » : toutes les applis dans le lanceur
                        self.tab = "launcher"
                        self.tabs["launcher"].set_view("running")
                        self.pinned = True
                    elif e.button() == Qt.MouseButton.RightButton:
                        self.dock_menu(g)
                    else:
                        self.dock_activate(g)
                    self.update()
            return
        if not self.pill_rect().contains(pos):
            return
        if e.button() == Qt.MouseButton.RightButton:
            self.tray_menu.popup(QCursor.pos())
            return
        for hit, setter, _v, track in reversed(self.sliders):
            if hit.contains(pos):
                self.drag = (track, setter)
                self._drag_to(pos)
                return
        for rect, fn in reversed(self.hits):
            if rect.contains(pos):
                fn()
                self.update()
                return
        for rect, paths, click in reversed(self.draggables):
            if rect.contains(pos):
                self._press = (pos, paths, click)  # clic ou glisser : décidé au mouvement / relâchement
                return
        if self.focus_field:
            self.unfocus(restore=False)
        if self.mode == "alert":
            a = self.alert or {}
            self.alert_until = 0
            goto = {"media": "home", "volume": "controls", "output": "controls", "clip": "clip", "timer": "timers",
                    "alarm": "timers", "pomo": "timers", "event": "agenda", "task": "tasks", "ci_fail": "dev",
                    "build_fail": "dev", "build_ok": "dev", "ci_ok": "dev", "phone": "phone", "phone_notif": "phone",
                    "phone_call": "phone", "phone_file": "files", "files": "files", "download": "files",
                    "launch": "launcher", "wallet": "wallet"}.get(a.get("kind"))
            if goto:
                self.tab = goto
                self.pinned = True
            return
        if self.mode in COMPACT_MODES:
            self.tab = {"cmedia": "home", "ctimer": "timers", "cmeet": "agenda", "cbuild": "dev"}.get(self.mode, self.tab)
            self.pinned = True
            if hasattr(self, "pin_action"):
                self.pin_action.setChecked(True)

    def _drag_to(self, pos):
        rect, setter = self.drag
        setter(max(0.0, min(1.0, (pos.x() - rect.left()) / rect.width())))

    def mouseMoveEvent(self, e):
        if self.drag:
            self._drag_to(QPointF(e.position()))
        elif self._press:
            pos, paths, _click = self._press
            if (QPointF(e.position()) - pos).manhattanLength() > 8:
                self._press = None
                self.start_file_drag(paths)

    def mouseReleaseEvent(self, e):
        if self.drag:
            self.drag = None
            self.refresh_visible()
        if self._press:
            _pos, _paths, click = self._press
            self._press = None
            click()

    # --- glisser-déposer de fichiers
    def start_file_drag(self, paths):
        """Fait glisser des fichiers de l'île vers une autre application (Explorateur, e-mail, navigateur…)."""
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        drag = QDrag(self)
        drag.setMimeData(md)
        pm = QPixmap(220, 36)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setBrush(QColor(0, 0, 0, 230))
        q.setPen(QPen(T.stroke2, 1))
        q.drawRoundedRect(QRectF(0.5, 0.5, 219, 35), 6, 6)
        q.setPen(T.text)
        q.setFont(font(9, W.Medium))
        name = os.path.basename(paths[0]) + (f"  +{len(paths) - 1}" if len(paths) > 1 else "")
        q.drawText(QRectF(12, 0, 200, 36), int(LEFT), name)
        q.end()
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        self.drag_out = True
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, Qt.DropAction.CopyAction)
        self.drag_out = False
        self.files.changed.emit()

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if self.drag_out or not md.hasUrls() or not any(u.isLocalFile() for u in md.urls()):
            e.ignore()
            return
        e.acceptProposedAction()
        self.drop_hover = True
        self.tab = "files"
        self.tabs["files"].set_view("shelf")

    def dragMoveEvent(self, e):
        if self.drop_hover:
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.drop_hover = False

    def dropEvent(self, e):
        self.drop_hover = False
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        n = self.files.add_to_shelf(paths)
        e.acceptProposedAction()
        self.pinned = True
        self.show_alert("files", f"{n} élément(s) en attente" if n else "Déjà sur l'étagère",
                        os.path.basename(paths[0]) if paths else "", T.accent, G["folder"])

    def copy_files(self, paths):
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QApplication.clipboard().setMimeData(md)
        self.show_alert("files", f"{len(paths)} fichier(s) copiés", "Collez-les dans l'Explorateur (Ctrl+V)",
                        T.accent, G["copy"], duration=2)

    # --- téléphone
    def on_phone_text(self, text):
        self._from_phone = text
        QApplication.clipboard().setText(text)
        self.show_alert("phone", "Reçu du téléphone", " ".join(text.split())[:70] + " · copié", T.accent, G["phone"])

    def on_clipboard_for_phone(self):
        ph = self.phone
        if not (ph.sync_clip and ph.running):
            return
        t = QApplication.clipboard().text()
        if t and t != getattr(self, "_from_phone", None) and (not ph.outbox or ph.outbox[0]["text"] != t):
            ph.push_text(t, "clip")

    def on_phone_alert(self, kind, title, sub, data):
        if kind == "phone_call":
            self.show_alert(kind, title, sub or "Appel entrant", T.success, G["phone"], duration=20,
                            action=("Lien", lambda: self.tabs["phone"]._open_link()))
        elif kind == "phone_file":
            self.show_alert(kind, title, sub, T.accent, G["phone"], duration=6,
                            action=("Ouvrir", lambda: self.files.open(data)))
        elif kind == "phone_err":
            self.show_alert(kind, title, sub, T.critical, G["error"], duration=6)
        else:
            self.show_alert(kind, title, sub, T.accent, G["bell"], duration=5)

    def on_remote(self, action, arg):
        keys = {"play": 0xB3, "next": 0xB0, "prev": 0xB1, "volup": 0xAF, "voldown": 0xAE, "mute": 0xAD,
                "left": 0x25, "right": 0x27, "space": 0x20}
        if action in keys:
            vk = keys[action]
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
        elif action == "open" and arg.lower().startswith(("http://", "https://")):
            webbrowser.open(arg)

    def on_files_alert(self, kind, title, path):
        if kind == "download":
            self.show_alert(kind, title, os.path.basename(path), T.success, "", duration=6,
                            action=("Ouvrir", lambda p=path: self.files.open(p)))
        else:
            self.show_alert(kind, title, path, T.accent, G["folder"])

    def wheelEvent(self, e):
        pos = QPointF(e.position())
        steps = e.angleDelta().y() / 120
        for hit, setter, val, _t in reversed(self.sliders):
            if hit.contains(pos):
                setter(max(0.0, min(1.0, val + steps * 0.04)))
                return
        for rect, key, mx in reversed(self.scroll_regions):
            if rect.contains(pos):
                cur, tgt = self.scrolls.get(key, (0.0, 0.0))
                self.scrolls[key] = (cur, max(0.0, min(mx, tgt - steps * 60)))
                return
        if self.mode in COMPACT_MODES:
            self.audio.set_volume(self.audio.volume() + steps * 0.04)

    def keyPressEvent(self, e):
        name = self.focus_field
        if not name:
            return
        tab = self.tabs.get(self.tab)
        if name in ("clip_search", "launch_search") and hasattr(tab, "key_event") and e.key() != Qt.Key.Key_Escape \
                and tab.key_event(e):
            self.update()
            return
        k = e.key()
        mods = e.modifiers()
        val = self.fields.get(name, "")
        on_submit, on_change = self.field_handlers.get(name, (None, None))
        changed = False
        if k == Qt.Key.Key_Escape:
            if val:
                self.fields[name] = ""
                changed = True
            else:
                self.unfocus()
                if self.pinned and not self.hovered:
                    self.close_island()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if on_submit and val.strip():
                if on_submit(val):
                    self.fields[name] = ""
                    changed = True
        elif k == Qt.Key.Key_Backspace:
            if mods & Qt.KeyboardModifier.ControlModifier:
                v = val.rstrip()
                self.fields[name] = v[: max(0, v.rfind(" ") + 1)]
            else:
                self.fields[name] = val[:-1]
            changed = True
        elif k == Qt.Key.Key_V and mods & Qt.KeyboardModifier.ControlModifier:
            txt = QApplication.clipboard().text()
            if name != "note_add":
                txt = " ".join(txt.split())
            self.fields[name] = val + txt
            changed = True
        elif e.text() and e.text().isprintable() and not (mods & Qt.KeyboardModifier.ControlModifier):
            self.fields[name] = val + e.text()
            changed = True
        if changed and on_change:
            on_change(self.fields.get(name, ""))
        self.update()

    # ------------------------------------------------------------ dessin
    def draw_art(self, p, rect, radius):
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
        if self.art:
            p.drawPixmap(rect.toRect(), self.art)
        else:
            p.fillRect(rect, T.layer2)
            self.ui.glyph(rect.center(), G["music"], rect.height() * 0.42, T.text3)
        p.restore()

    def draw_eq(self, p, rect, color):
        n = 4
        bw = rect.width() / (n * 2 - 1)
        t = time.time() - self.t0
        playing = self.media and self.media["playing"]
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for i in range(n):
            k = 0.25 + 0.75 * abs(math.sin(t * (5.1 + i * 1.7) + i * 1.3) * math.sin(t * (2.3 + i * 0.6))) \
                if playing else 0.18
            bh = max(bw, rect.height() * k)
            p.drawRoundedRect(QRectF(rect.left() + i * bw * 2, rect.center().y() - bh / 2, bw, bh), bw / 2, bw / 2)
        p.restore()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        ui = self.ui
        ui.p = p

        self.paint_dock(p)
        r = self.pill_rect()
        radius = R_OPEN if self.h > 60 else min(R_COMPACT, r.height() / 2)
        self.paint_shadow(p, r, radius)
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        p.fillPath(path, T.bg)
        p.setPen(QPen(T.stroke2 if T.dark else T.stroke, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        # découpe rectangulaire (rapide) : un chemin arrondi rendrait chaque texte ~8× plus lent
        p.setClipRect(r.adjusted(2, 2, -2, -2))

        self.hits, self.sliders, self.scroll_regions = [], [], []
        self.draggables = []
        self.field_handlers = {}
        t = time.time() - self.mode_t
        a_new = smooth((t - 0.03) / 0.20)
        a_old = 1 - smooth(t / 0.10)
        new_exp, old_exp = self.mode.startswith("tab:"), self.prev_mode.startswith("tab:")
        both = new_exp and old_exp
        cx = r.center().x()

        # barre d'onglets fixe quand on passe d'un onglet à l'autre
        if both:
            self._reg = True
            p.setOpacity(1.0)
            self.paint_tabbar(ui, r)

        # ancien contenu : toujours depuis une image en cache (évite de tout redessiner 2 fois)
        if a_old > 0 and self.prev_mode != self.mode:
            self._reg = False
            p.setOpacity(a_old)
            p.save()
            if both:
                p.translate(-self.slide_dir * 16 * (1 - a_old), 0)
            if old_exp:
                pm, tw, th = self.content_pixmap(self.prev_mode)
                skip = TAB_H if both else 0
                p.drawPixmap(QRectF(cx - tw / 2, r.top() + skip, tw, th - skip), pm,
                             QRectF(0, skip, tw, th - skip))
            else:
                self.paint_mode(ui, self.prev_mode, r)
            p.restore()

        # nouveau contenu : image en cache pendant que l'île change de taille, dessin direct ensuite
        if a_new > 0:
            p.setOpacity(a_new)
            p.save()
            if both:
                p.translate(self.slide_dir * 16 * (1 - a_new), 0)
            else:
                s = 0.95 + 0.05 * a_new
                p.translate(cx, r.top())
                p.scale(s, s)
                p.translate(-cx, -r.top())
            if new_exp and self.moving:
                self._reg = False
                pm, tw, th = self.content_pixmap(self.mode)
                skip = TAB_H if both else 0
                p.drawPixmap(QRectF(cx - tw / 2, r.top() + skip, tw, th - skip), pm, QRectF(0, skip, tw, th - skip))
            else:
                self._reg = a_new > 0.6
                if new_exp and not both:
                    self.paint_tabbar(ui, r)
                self.paint_mode(ui, self.mode, r)
            p.restore()
        self._reg = False
        p.end()

    def warmup(self, keys=None):
        keys = list(self.tab_keys) if keys is None else keys
        if not keys:
            return
        key = keys.pop(0)
        if not self.is_open:
            try:
                self.content_pixmap("tab:" + key)
                tab = self.tabs[key]
                for v in [v for v, _ in getattr(__import__("tab_" + key), "VIEWS", [])]:
                    old = tab.view
                    tab.view = v
                    self._cc.pop("tab:" + key, None)
                    self.content_pixmap("tab:" + key)
                    tab.view = old
            except Exception:
                pass
            self._cc.pop("tab:" + key, None)
        else:
            keys.insert(0, key)
        QTimer.singleShot(120, lambda: self.warmup(keys))

    def content_pixmap(self, mode):
        """Rendu (onglets + contenu) mis en cache ~0,4 s pour les animations."""
        tab = self.tabs[mode[4:]]
        tw, th = EW, TAB_H + tab.height()
        key = (mode, tw, th, T.dark)
        c = self._cc.get(mode)
        if c and c[0] == key and time.time() - c[2] < 0.4:
            return c[1], tw, th
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(tw * dpr) + 1, int(th * dpr) + 1)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        main_p, reg = self.ui.p, self._reg
        self.ui.p, self._reg = q, False
        rr = QRectF(0, 0, tw, th)
        q.setClipRect(rr.adjusted(2, 2, -2, -2))
        self.paint_tabbar(self.ui, rr)
        self.paint_mode(self.ui, mode, rr)
        q.end()
        self.ui.p, self._reg = main_p, reg
        self._cc[mode] = (key, pm, time.time())
        return pm, tw, th

    # ------------------------------------------------------------ dock des applications ouvertes
    @property
    def dock_enabled(self):
        return settings.get("dock", True)

    def dock_layout(self):
        """Rectangle du dock (à droite de la pilule) et cases [(rect, groupe | None pour « +N »)]."""
        apps = self.launcher.running
        if not apps or self.dock_alpha <= 0.01 and not (self.dock_enabled and not self.is_open):
            return None, []
        pr = self.pill_rect()
        room = int((WIN_W - 16 - (pr.right() + 8) - 8) // DOCK_CELL)
        shown = apps[:max(1, min(DOCK_MAX, room))]
        extra = len(apps) - len(shown)
        if extra and len(shown) > 1:
            shown = shown[:-1]
            extra += 1
        n = len(shown) + (1 if extra else 0)
        dr = QRectF(pr.right() + 8, PAD, 8 + n * DOCK_CELL, 34)
        cells = [(QRectF(dr.left() + 4 + i * DOCK_CELL, dr.top() + 2, DOCK_CELL, 30), g)
                 for i, g in enumerate(shown + ([None] if extra else []))]
        self._dock_extra = extra
        return dr, cells

    def paint_dock(self, p):
        dr, cells = self.dock_layout()
        if dr is None or self.dock_alpha <= 0.01:
            return
        ui = self.ui
        p.save()
        p.setOpacity(self.dock_alpha)
        # glisse légèrement depuis la pilule à l'apparition
        p.translate(-10 * (1 - self.dock_alpha), 0)
        self.paint_shadow(p, dr, R_COMPACT)
        path = QPainterPath()
        path.addRoundedRect(dr, R_COMPACT, R_COMPACT)
        p.fillPath(path, T.bg)
        p.setPen(QPen(T.stroke2, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(dr.adjusted(0.5, 0.5, -0.5, -0.5), R_COMPACT, R_COMPACT)
        fg = user32.GetForegroundWindow()
        label = None
        for i, (rr, g) in enumerate(cells):
            c = rr.center()
            hov = i == self.dock_hover
            if hov:
                ui.rect(rr.adjusted(2, 1, -2, -1), T.hover, 6)
            if g is None:
                ui.text(rr, f"+{self._dock_extra}", font(8, W.DemiBold), T.text2, CENTER)
                if hov:
                    label = (c, "Toutes les applis ouvertes")
                continue
            size = 22 if hov else 20
            minimized = all(w["min"] for w in g["windows"])
            if minimized:
                p.setOpacity(self.dock_alpha * 0.5)
            ui.file_icon(QRectF(c.x() - size / 2, c.y() - size / 2 - 1, size, size), g["exe"], chr(0xE71D))
            p.setOpacity(self.dock_alpha)
            active = any(w["hwnd"] == fg for w in g["windows"])
            if active:  # indicateur d'appli au premier plan, comme la barre des tâches
                ui.rect(QRectF(c.x() - 6, rr.bottom() - 2, 12, 2.5), T.accent, 1.25)
            elif len(g["windows"]) > 1:
                ui.rect(QRectF(c.x() - 2, rr.bottom() - 2, 4, 2.5), T.text3, 1.25)
            if hov:
                n = len(g["windows"])
                label = (c, g["name"] + (f" · {n} fenêtres" if n > 1 else ""))
        if label:
            c, txt = label
            f = font(8, W.Medium)
            w = ui.tw(txt, f) + 18
            lr = QRectF(c.x() - w / 2, dr.bottom() + 6, w, 22)
            if lr.right() > WIN_W - 4:
                lr.moveRight(WIN_W - 4)
            ui.rect(lr, T.bg, 6, T.stroke2)
            ui.text(lr, txt, f, T.text, CENTER)
        p.restore()

    def dock_activate(self, g):
        """Clic : affiche l'appli ; si elle est déjà au premier plan, la réduit (comme la barre des tâches)."""
        fg = user32.GetForegroundWindow()
        hwnds = [w["hwnd"] for w in g["windows"]]
        if fg in hwnds and not user32.IsIconic(fg):
            self.launcher.minimize_window(fg)
        else:
            S.activate_window(hwnds[0])
        QTimer.singleShot(300, self.launcher.refresh_running)

    def dock_menu(self, g):
        """Clic droit : fenêtres de l'appli et actions."""
        L = self.launcher
        m = QMenu()
        m.setStyleSheet(MENU_QSS)
        head = m.addAction(g["name"] + f"  ·  {g['mem'] / 2 ** 20:.0f} Mo")
        head.setEnabled(False)
        m.addSeparator()
        if len(g["windows"]) > 1:
            for w in g["windows"]:
                t = w["title"] if len(w["title"]) < 60 else w["title"][:57] + "…"
                a = m.addAction(("◦ " if w["min"] else "• ") + t)
                a.triggered.connect(lambda _=False, h=w["hwnd"]: S.activate_window(h))
            m.addSeparator()
        m.addAction("Afficher").triggered.connect(lambda: S.activate_window(g["windows"][0]["hwnd"]))
        m.addAction("Réduire").triggered.connect(lambda: [L.minimize_window(w["hwnd"]) for w in g["windows"]])
        m.addAction("Fermer").triggered.connect(lambda: L.close_app(g))
        m.addSeparator()

        def force():
            if QMessageBox.question(None, "Dynamic Island", f"Forcer l'arrêt de {g['name']} ?\n"
                                    "Les données non enregistrées seront perdues.") == QMessageBox.StandardButton.Yes:
                L.kill_app(g)
        m.addAction("Forcer l'arrêt…").triggered.connect(force)
        m.exec(QCursor.pos())
        L.refresh_running()

    _shadow_cache = {}

    def paint_shadow(self, p, r, radius):
        """Ombre douce Windows 11 en 9 morceaux, précalculée (évite 8 formes arrondies par image)."""
        m = 9
        key = (int(radius), T.shadow.alpha())
        pm = self._shadow_cache.get(key)
        c = m + int(radius) + 2          # taille d'un coin
        if pm is None:
            size = 2 * c + 2
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setPen(Qt.PenStyle.NoPen)
            inner = QRectF(m, m, size - 2 * m, size - 2 * m)
            for i in range(1, m):
                q.setBrush(QColor(0, 0, 0, int(T.shadow.alpha() * (1 - i / m) ** 2 * 0.5)))
                q.drawRoundedRect(inner.adjusted(-i, -i, i, i), radius + i, radius + i)
            q.end()
            self._shadow_cache[key] = pm
        size = pm.width()
        o = QRectF(r.left() - m, r.top() - m + 2, r.width() + 2 * m, r.height() + 2 * m + 1)
        if o.width() < 2 * c or o.height() < 2 * c:
            return
        mid = size - 2 * c
        L, T_, R, B = o.left(), o.top(), o.right(), o.bottom()
        pieces = [  # (cible, source)
            (QRectF(L, T_, c, c), QRectF(0, 0, c, c)),
            (QRectF(R - c, T_, c, c), QRectF(size - c, 0, c, c)),
            (QRectF(L, B - c, c, c), QRectF(0, size - c, c, c)),
            (QRectF(R - c, B - c, c, c), QRectF(size - c, size - c, c, c)),
            (QRectF(L + c, T_, o.width() - 2 * c, c), QRectF(c, 0, mid, c)),
            (QRectF(L + c, B - c, o.width() - 2 * c, c), QRectF(c, size - c, mid, c)),
            (QRectF(L, T_ + c, c, o.height() - 2 * c), QRectF(0, c, c, mid)),
            (QRectF(R - c, T_ + c, c, o.height() - 2 * c), QRectF(size - c, c, c, mid)),
        ]
        for tgt, src in pieces:
            p.drawPixmap(tgt, pm, src)

    def paint_mode(self, ui, mode, r):
        if mode.startswith("tab:"):
            cr = QRectF(r.left(), r.top() + TAB_H, r.width(), max(0, r.height() - TAB_H))
            ui.p.save()
            ui.p.setClipRect(cr, Qt.ClipOperation.IntersectClip)
            self.tabs[mode[4:]].paint(ui, cr)
            ui.p.restore()
        else:
            getattr(self, "paint_" + mode)(ui, r)

    # --- barre d'onglets
    def paint_tabbar(self, ui, r):
        y = r.top()
        bw, bh, gap = 34, 32, 2
        n = len(self.tab_keys)
        x0 = r.right() - 84 - n * (bw + gap)
        hov_label = None
        for i, key in enumerate(self.tab_keys):
            t = self.tabs[key]
            br = QRectF(x0 + i * (bw + gap), y + 7, bw, bh)
            on = key == self.tab
            if ui.hovering(br):
                hov_label = t.label
                if not on:
                    ui.rect(br, T.hover, 4)
            if on:
                ui.rect(br, T.layer2, 4)
            ui.glyph(br.center(), t.glyph, 14, T.text if on else T.text2)
            ui.hit(br, lambda k=key: self.set_tab(k))
        ix = x0 + self.tab_x * (bw + gap) + bw / 2
        ui.rect(QRectF(ix - 8, y + 7 + bh - 3, 16, 3), T.accent, 1.5)
        ui.text(QRectF(r.left() + 18, y + 6, x0 - r.left() - 24, 34), hov_label or self.tabs[self.tab].label,
                font(10, W.DemiBold, True), T.text)
        # heure + batterie
        ui.text(QRectF(r.right() - 78, y + 6, 44, 34), dt.datetime.now().strftime("%H:%M"), font(9, W.DemiBold),
                T.text, RIGHT)
        if self.battery:
            pct, plugged = self.battery
            col = T.success if plugged else (T.critical if pct <= 20 else T.text2)
            ui.glyph(QPointF(r.right() - 20, y + 23), G["charging"] if plugged else G["battery"], 15, col)
            ui.hit(QRectF(r.right() - 34, y + 8, 28, 30), lambda: self.show_alert(
                "battery", f"Batterie {pct} %", "En charge" if plugged else "Sur batterie", col, G["battery"]))
        ui.rect(QRectF(r.left() + 1, y + TAB_H - 1, r.width() - 2, 1), T.stroke, 0)

    # --- états compacts
    def indicators(self, ui, r, x):
        p = ui.p
        p.setPen(Qt.PenStyle.NoPen)
        for busy, col in ((self.cam_busy, T.success), (self.mic_busy, T.orange)):
            if busy:
                p.setBrush(col)
                p.drawEllipse(QPointF(x, r.center().y()), 3.2, 3.2)
                x -= 11
        if self.timers.focus:
            ui.glyph(QPointF(x - 2, r.center().y()), G["moon"], 10, T.accent)
            x -= 16
        return x

    def paint_compact(self, ui, r):
        ui.text(r, dt.datetime.now().strftime("%H:%M"), font(10, W.DemiBold), T.text, CENTER)
        x = self.indicators(ui, r, r.right() - 14)
        if self.battery and self.battery[1] and x == r.right() - 14:
            ui.glyph(QPointF(r.right() - 16, r.center().y()), G["bolt"], 11, T.success)
        if self.caps:
            ui.glyph(QPointF(r.left() + 16, r.center().y()), G["keyboard"], 11, T.success)

    def paint_cmedia(self, ui, r):
        if not self.media:
            return
        self.draw_art(ui.p, QRectF(r.left() + 7, r.top() + 6, 22, 22), 5)
        ui.text(QRectF(r.left() + 36, r.top(), r.width() - 90, r.height()), self.media["title"], font(8.5, W.Medium),
                T.text2)
        self.draw_eq(ui.p, QRectF(r.right() - 30, r.top() + 10, 18, 14), self.accent)
        self.indicators(ui, r, r.right() - 42)

    def paint_ctimer(self, ui, r):
        act = self.timers.active()
        if not act:
            return
        label, rem, frac, kind = act
        col = T.success if kind == "pomo" and self.timers.pomo["phase"] != "work" else T.accent
        c = QPointF(r.left() + 19, r.center().y())
        if frac is not None:
            ui.ring(c, 9, frac, col, 2.5)
        else:
            ui.glyph(c, G["timer"], 12, col)
        ui.text(QRectF(r.left() + 36, r.top(), 110, r.height()), label, font(8.5, W.Medium), T.text2)
        ui.text(QRectF(r.right() - 96, r.top(), 82, r.height()), fmt_dur(rem), font(10.5, W.DemiBold), col, RIGHT)

    def paint_cmeet(self, ui, r):
        o = self.agenda.next_timed()
        if not o:
            return
        now = time.time()
        ui.glyph(QPointF(r.left() + 18, r.center().y()), G["video"] if o.get("meet_url") else G["calendar"], 12, T.accent)
        ui.text(QRectF(r.left() + 34, r.top(), r.width() - 130, r.height()), o["title"], font(8.5, W.Medium), T.text)
        txt = "en cours" if o["start"] <= now else until(o["start"] - now)
        ui.text(QRectF(r.right() - 100, r.top(), 86, r.height()), txt, font(8.5, W.DemiBold), T.accent, RIGHT)

    def paint_cbuild(self, ui, r):
        b = self.dev.build
        if not b:
            return
        ang = (time.time() * 360) % 360
        p = ui.p
        c = QPointF(r.left() + 19, r.center().y())
        p.setPen(QPen(T.caution, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(c.x() - 8, c.y() - 8, 16, 16), int(-ang * 16), 270 * 16)
        ui.text(QRectF(r.left() + 36, r.top(), r.width() - 90, r.height()), "Build " + (b.get("project") or ""),
                font(8.5, W.Medium), T.text2)
        ui.text(QRectF(r.right() - 60, r.top(), 46, r.height()), f"{int(time.time() - b['start'])} s",
                font(9, W.DemiBold), T.caution, RIGHT)

    def paint_alert(self, ui, r):
        a = self.alert
        if not a:
            return
        c = QPointF(r.left() + 34, r.center().y())
        if a["kind"] == "media":
            self.draw_art(ui.p, QRectF(c.x() - 20, c.y() - 20, 40, 40), 6)
        else:
            ui.rect(QRectF(c.x() - 20, c.y() - 20, 40, 40), T.tint(a["color"], 45), 6)
            ui.glyph(c, a["glyph"] or G["info"], 17, a["color"])
        tx = r.left() + 66
        right = 96 if a.get("action") else (50 if a["kind"] == "media" else 18)
        tw = r.right() - tx - right
        if a.get("bar") is not None:
            ui.text(QRectF(tx, r.top() + 10, tw, 20), a["title"], font(10, W.DemiBold))
            ui.bar(QRectF(tx, r.top() + 38, tw - 46, 4), a["bar"])
            ui.text(QRectF(r.right() - 66, r.top() + 29, 48, 22), f"{a['bar'] * 100:.0f}", font(9, W.DemiBold),
                    T.text, RIGHT)
            return
        ui.text(QRectF(tx, r.top() + 12, tw, 20), a["title"], font(10, W.DemiBold))
        ui.text(QRectF(tx, r.top() + 32, tw, 18), a["subtitle"], font(8.5), T.text2)
        if a["kind"] == "media":
            self.draw_eq(ui.p, QRectF(r.right() - 40, r.center().y() - 9, 20, 18), self.accent)
        act = a.get("action")
        if act:
            def run(fn=act[1]):
                fn()
                self.alert_until = 0
            ui.button(QRectF(r.right() - 92, r.center().y() - 15, 80, 30), act[0], run, accent=True)

    def shutdown(self):
        self.restore_taskbar()
        user32.UnregisterHotKey(self.hwnd, HOTKEY_ID)
        user32.UnregisterHotKey(self.hwnd, HOTKEY_LAUNCH)
        if self.timers.focus:
            self.set_focus(False)
        self.worker.stop()
        self.radio.stop()
        try:
            self.clip.save()
        except Exception:
            pass


# ================================================================== démarrage auto
def autostart_command():
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "island_watchdog.pyw")
    return f'"{pyw}" "{guard}"'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass


def main():
    ctypes.windll.kernel32.CreateMutexW(None, False, "DynamicIsland_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:
        return
    ctypes.windll.winmm.timeBeginPeriod(1)
    sys.setswitchinterval(0.001)  # les threads de fond ne bloquent plus l'animation

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    island = Island()

    tray = QSystemTrayIcon(make_tray_icon(), app)
    tray.setToolTip("Dynamic Island")
    island.tray = tray
    menu = QMenu()
    pin = QAction("Garder ouvert", menu, checkable=True)
    pin.toggled.connect(lambda v: setattr(island, "pinned", v))
    auto = QAction("Démarrer avec Windows", menu, checkable=True)
    if not settings.get("autostart_done"):  # île permanente : démarrage avec Windows activé une fois par défaut
        set_autostart(True)
        settings.set("autostart_done", True)
    elif autostart_enabled():
        set_autostart(True)  # met à jour la commande (passage par le gardien)
    auto.setChecked(autostart_enabled())
    auto.toggled.connect(set_autostart)
    dock_a = QAction("Applis ouvertes à côté de l'île", menu, checkable=True)
    dock_a.setChecked(island.dock_enabled)
    dock_a.toggled.connect(lambda v: settings.set("dock", v))
    menu.setStyleSheet(MENU_QSS)
    tb = QAction("Masquer la barre des tâches", menu, checkable=True)
    tb.setChecked(island.taskbar_hidden)
    tb.toggled.connect(island.set_taskbar_hidden)

    clip_menu = menu.addMenu("Presse-papiers")
    open_clip = QAction("Ouvrir  (Ctrl+Alt+V)", clip_menu)
    open_clip.triggered.connect(island.open_clipboard)
    pause = QAction("Mettre l'historique en pause", clip_menu, checkable=True)
    pause.toggled.connect(lambda v: setattr(island.clip, "paused", v))

    def clear():
        if QMessageBox.question(None, "Dynamic Island", "Effacer tout l'historique du presse-papiers ?\n"
                                "(les éléments épinglés sont conservés)") == QMessageBox.StandardButton.Yes:
            island.clip.clear()

    clear_a = QAction("Effacer l'historique…", clip_menu)
    clear_a.triggered.connect(clear)
    for a in (open_clip, pause, clear_a):
        clip_menu.addAction(a)

    sync_a = QAction("Synchroniser via un dossier cloud…", menu)
    stop_sync = QAction("Arrêter la synchronisation", menu)

    def refresh_sync():
        d = settings.get("sync_dir")
        sync_a.setText(f"Synchronisé : {d}" if d else "Synchroniser via un dossier cloud…")
        stop_sync.setVisible(bool(d))

    def choose_sync():
        d = QFileDialog.getExistingDirectory(None, "Dossier synchronisé (OneDrive, Google Drive, Dropbox…)",
                                             os.environ.get("OneDrive", os.path.expanduser("~")))
        if d:
            island.clip.set_sync_dir(d)
            Collection.save_all()
            refresh_sync()

    def disable_sync():
        island.clip.set_sync_dir(None)
        Collection.save_all()
        refresh_sync()

    sync_a.triggered.connect(choose_sync)
    stop_sync.triggered.connect(disable_sync)
    refresh_sync()

    quit_action = QAction("Quitter", menu)

    def quit_app():
        island.shutdown()
        tray.hide()
        app.quit()

    quit_action.triggered.connect(quit_app)
    menu.addAction(pin)
    menu.addAction(auto)
    menu.addAction(tb)
    menu.addAction(dock_a)
    menu.addSeparator()
    menu.addAction(sync_a)
    menu.addAction(stop_sync)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()
    island.tray_menu = menu
    island.pin_action = pin

    QApplication.primaryScreen().geometryChanged.connect(lambda _: island.place())
    island.show()
    S.set_exstyle(island.hwnd, S.WS_EX_NOACTIVATE, True)
    island.apply_taskbar()
    app.aboutToQuit.connect(island.restore_taskbar)
    code = app.exec()
    ctypes.windll.winmm.timeEndPeriod(1)
    sys.exit(code)


if __name__ == "__main__":
    main()
