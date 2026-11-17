"""Main Dynamic Island window: state, layout targets and the animation loop.

Behaviour is split into mixins: alerts (alerts.py), Windows integration (system_tasks.py),
user input (input.py) and painting (ui/components/painting.py)."""
import ctypes
import time
import webbrowser

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QApplication, QWidget

from dynamic_island.core.localization import on_language_changed, translate as tr
from dynamic_island.core.utilities.animation import spring
from dynamic_island.engines.agenda import Agenda
from dynamic_island.engines.binance import Binance
from dynamic_island.engines.clipboard import ClipboardHistory
from dynamic_island.engines.devtools import Dev
from dynamic_island.engines.files import Files
from dynamic_island.engines.hotspot import Hotspot
from dynamic_island.engines.infos import Infos
from dynamic_island.engines.launcher import Launcher
from dynamic_island.engines.media import MediaWorker
from dynamic_island.engines.network import Networks
from dynamic_island.engines.tasks import Tasks
from dynamic_island.engines.timers import Timers
from dynamic_island.infrastructure.storage.collection import Collection
from dynamic_island.services import system
from dynamic_island.services.phone import Phone
from dynamic_island.ui.components.drawing import UI
from dynamic_island.ui.components.painting import IslandPainting
from dynamic_island.ui.tabs import TABS
from dynamic_island.ui.themes import G, T
from dynamic_island.ui.windows.alerts import IslandAlerts
from dynamic_island.ui.windows.input import IslandInput
from dynamic_island.ui.windows.layout import (
    ALERT,
    COMPACT,
    COMPACT_BUILD,
    COMPACT_MEDIA,
    COMPACT_MEET,
    COMPACT_TIMER,
    DOCK_MAX,
    EW,
    HOTKEY_ID,
    HOTKEY_LAUNCH,
    HOVER_DELAY,
    LEAVE_DELAY,
    PAD,
    TAB_H,
    TOP_MARGIN,
    WIN_H,
    WIN_W,
)
from dynamic_island.ui.windows.system_tasks import IslandSystem

user32 = ctypes.windll.user32


class Island(IslandInput, IslandAlerts, IslandSystem, IslandPainting, QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(WIN_W, WIN_H)
        self.setWindowTitle(tr("app.name"))
        self.place()
        self.hwnd = int(self.winId())
        system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, True)
        self.click_through = None
        self.ui = UI(self)

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

        self.media = None
        self.media_at = 0.0
        self.media_key = None
        self.first_media = True
        self.art = None
        self.thumb_bytes = None
        self.accent = QColor(T.accent)
        self.media_exe = None      # playing app executable, used for its icon
        self._media_app_key = None

        self.audio = system.Audio()
        self.bright = system.Brightness()
        self.dnd = system.DoNotDisturb()
        self.radio = system.RadioWorker()
        self.radio.updated.connect(self.on_radios)
        self.wifi = self.bt = None
        self.night = system.night_light_on()
        self.night_ok = system.night_light_supported()
        self.cam_allowed = system.camera_allowed()
        self.cam_busy = self.mic_busy = False
        self.caps, self.num = system.caps_lock(), system.num_lock()
        self.vol, self.muted = 0.0, False  # real values once audio is loaded (_finish_startup)
        self.out_id = None
        psutil.cpu_percent(None)
        self.battery = None
        self.plugged = None
        self.low_warned = False
        self._dnd_by_focus = False

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
        self.hotspot.alert.connect(lambda title, subtitle, ok: self.show_alert(
            "hotspot", title, subtitle, T.success if ok else T.critical, chr(0xE88A), duration=5))
        self.net.alert.connect(lambda kind, title, subtitle, ok: self.show_alert(
            "net", title, subtitle, T.success if ok else T.critical,
            G["wifi"] if kind == "wifi" else G["bt"], duration=4))
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

        self.tabs = {}
        for cls in TABS:
            t = cls(self)
            self.tabs[t.key] = t
        self.tab_keys = list(self.tabs)
        self.tab = "home"
        self.tab_x = 0.0
        self._language_unsubscribe = on_language_changed(self._language_changed)

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

        # pre-warm each tab's fonts (avoids a stutter on first display)
        QTimer.singleShot(1500, self.warmup)

        self.worker = MediaWorker()
        self.worker.updated.connect(self.on_media)
        self._started = False
        QTimer.singleShot(1000, self._finish_startup)  # fallback if the first frame is never painted
        user32.RegisterHotKey(self.hwnd, HOTKEY_ID, 0x0002 | 0x0001 | 0x4000, 0x56)  # Ctrl+Alt+V
        user32.RegisterHotKey(self.hwnd, HOTKEY_LAUNCH, 0x0002 | 0x0001 | 0x4000, 0x20)  # Ctrl+Alt+Space

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._started:
            QTimer.singleShot(0, self._finish_startup)

    def _finish_startup(self):
        """Second startup phase, run right after the first frame is on screen: the slow
        Windows connections (audio endpoints, media session, radios, system state)."""
        if self._started:
            return
        self._started = True
        self.audio.load()
        self.vol, self.muted = self.audio.volume(), self.audio.muted()
        self.out_id = self.audio.default_id()
        self.update_stats()
        self.worker.start()
        self.radio.start()
        self.update()

    def _language_changed(self, _language):
        """Refresh translated labels and discard cached translated pixmaps."""
        self.setWindowTitle(tr("app.name"))
        self._cc.clear()
        self.update()

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
            system.set_exstyle(self.hwnd, system.WS_EX_TRANSPARENT, through)
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
        # repaint only when something changes (mouse, animation, live content)
        moved = self.mouse != getattr(self, "_last_mouse", None)
        self._last_mouse = QPointF(self.mouse)
        since = now - getattr(self, "_last_paint", 0)
        need = (animating or self.drag or (inside and moved) or dock_changed or int(now) != int(now - dt_)
                or (live and since > (0.033 if self.media and self.media["playing"] else 0.25))
                or (self.is_open and since > 0.5))
        if need:
            self._last_paint = now
            # refresh region: current + previous island (+ shadow), not the whole window
            r = self.pill_rect().adjusted(-14, -PAD, 14, 14).toAlignedRect()
            if dock_r is not None or self.dock_alpha > 0:  # dock and its hover label
                r = r.united(QRectF(self.pill_rect().right(), 0, WIN_W - self.pill_rect().right(), 100).toAlignedRect())
            prev = getattr(self, "_last_dirty", r)
            self._last_dirty = r
            self.update(r.united(prev))


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
        self.show_alert("clip", tr("common.copied"), text.split("\n")[0][:60], T.accent, G["copy"], duration=1.4)

    def copy_item(self, item):
        if self.clip.copy(item):
            self.show_alert("clip", tr("common.copied"), (item.get("text") or "").split("\n")[0][:60],
                            T.accent, G["copy"], duration=1.4)

    def paste_item(self, item):
        target = self.prev_fg if self.focus_field else user32.GetForegroundWindow()
        if not target or target == self.hwnd:
            target = self.prev_fg
        if not self.clip.copy(item):
            return
        self.close_island(restore_focus=False)
        if target:
            system.force_foreground(target)
        QTimer.singleShot(120, system.send_ctrl_v)
        self.show_alert("clip", tr("island.clipboard.pasted"), (item.get("text") or "").split("\n")[0][:60],
                        T.success, G["clip"], duration=1.4)

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

    def focus(self, name):
        if self.focus_field is None:
            fg = user32.GetForegroundWindow()
            if fg and fg != self.hwnd:
                self.prev_fg = fg
            system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, False)
            system.force_foreground(self.hwnd)
            self.activateWindow()
            self.setFocus()
        self.focus_field = name

    def unfocus(self, restore=True):
        if self.focus_field is None:
            return
        self.focus_field = None
        system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, True)
        if restore and self.prev_fg:
            system.force_foreground(self.prev_fg)

    def shutdown(self):
        unsubscribe = getattr(self, "_language_unsubscribe", None)
        if unsubscribe:
            unsubscribe()
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
