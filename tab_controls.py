"""Onglet Contrôles : paramètres rapides façon Windows 11."""
import time

from PySide6.QtCore import QPointF, QRectF, QTimer

import system as S
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT

APP_ROW = 30


class ControlsTab:
    key, label, glyph = "controls", "Contrôles", G["controls"]

    def __init__(self, isl):
        self.isl = isl
        self.picker = False
        self.confirm = None
        self.apps = []
        self.outputs = []

    def height(self):
        rows = len(self.outputs) if self.picker else len(self.apps)
        rows = max(1, min(4, rows))
        return 8 + 2 * 66 + 8 + 76 + 26 + rows * APP_ROW + 8 + 30 + 8

    def on_open(self):
        # après l'animation d'ouverture : l'énumération audio (COM) prend ~60 ms
        QTimer.singleShot(260, self.refresh)

    def refresh(self, brightness=True):
        isl = self.isl
        self.apps = isl.audio.apps()
        if self.picker:
            self.outputs = isl.audio.outputs()
        if brightness:
            isl.bright.request_refresh()

    # ------------------------------------------------------------------ actions
    def toggle_picker(self):
        self.picker = not self.picker
        self.isl.scrolls.pop("ctl_list", None)
        if self.picker:
            self.outputs = self.isl.audio.outputs()

    def choose_output(self, dev_id):
        isl = self.isl
        isl.audio.set_output(dev_id)
        isl.out_id = isl.audio.default_id()
        isl.vol = isl.audio.volume()
        self.picker = False

    def do_sleep(self):
        if self.confirm and self.confirm > time.time():
            self.confirm = None
            self.isl.close_island(restore_focus=False)
            QTimer.singleShot(400, S.sleep_pc)
        else:
            self.confirm = time.time() + 3

    def do_lock(self):
        self.isl.close_island(restore_focus=False)
        S.lock_pc()

    # ------------------------------------------------------------------ dessin
    def paint(self, ui, cr):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top() + 4
        cols = 5
        gap = 8
        tw = (x1 - x0 - gap * (cols - 1)) / cols
        mic_on = isl.audio.mic_available() and not isl.audio.mic_muted()
        conf = self.confirm and self.confirm > time.time()
        head = isl.headphones()
        tiles = [
            (G["wifi"], "Wi-Fi", bool(isl.wifi), lambda: isl.toggle_radio("wifi"), False, isl.wifi is not None, None),
            (G["bt"], "Bluetooth", bool(isl.bt), lambda: isl.toggle_radio("bluetooth"), False, isl.bt is not None, None),
            (G["plane"], "Mode avion", isl.airplane_on(), isl.toggle_airplane, False, True, None),
            (G["night"], "Éclairage nocturne", isl.night, isl.toggle_night, False, isl.night_ok, None),
            (G["moon"], "Ne pas déranger", isl.dnd.on, isl.dnd.toggle, False, True, None),
            (G["mic"], "Micro" if mic_on else "Micro coupé", mic_on, isl.audio.toggle_mic, not mic_on,
             isl.audio.mic_available(), None),
            (G["cam"], "Caméra" if isl.cam_allowed else "Caméra bloquée", isl.cam_allowed, isl.toggle_camera,
             not isl.cam_allowed, True, None),
            (G["headphone"] if head else G["speaker"], "Sortie audio", self.picker, self.toggle_picker, False, True, None),
            (G["lock"], "Verrouiller", False, self.do_lock, False, True, None),
            (G["power"], "Confirmer ?" if conf else "Veille", bool(conf), self.do_sleep, False, True, T.critical),
        ]
        for i, (g, label, on, fn, slash, enabled, color) in enumerate(tiles):
            r = QRectF(x0 + (i % cols) * (tw + gap), y + (i // cols) * 66, tw, 62)
            ui.tile(r, g, label, on, fn, slash, enabled, color)
        y += 2 * 66 + 8

        # curseurs
        sx0, sx1 = x0 + 40, x1 - 50
        vol = 0 if isl.muted else isl.vol
        ui.icon_button(QPointF(x0 + 14, y + 16), G["mute"] if isl.muted else G["vol"], isl.audio.toggle_mute, 14, T.text, 30)
        ui.slider(QRectF(sx0, y + 6, sx1 - sx0, 20), vol, isl.audio.set_volume)
        ui.text(QRectF(sx1 + 8, y, 42, 32), f"{vol * 100:.0f}", font(9, W.DemiBold), T.text, RIGHT)
        y += 38
        bv = isl.bright.value
        ui.glyph(QPointF(x0 + 14, y + 16), G["sun"], 14, T.text if bv is not None else T.disabled)
        if bv is not None:
            ui.slider(QRectF(sx0, y + 6, sx1 - sx0, 20), bv / 100, lambda v: isl.bright.set(v * 100))
            ui.text(QRectF(sx1 + 8, y, 42, 32), f"{bv:.0f}", font(9, W.DemiBold), T.text, RIGHT)
        else:
            ui.text(QRectF(sx0, y, sx1 - sx0, 32), "Luminosité non disponible sur cet écran", font(8.5), T.text3)
        y += 38

        # liste
        title = "Choisir la sortie audio" if self.picker else "Volume par application"
        ui.text(QRectF(x0, y, 300, 20), title, font(8.5, W.DemiBold))
        y += 24
        rows = self.outputs if self.picker else self.apps
        n = max(1, min(4, len(rows)))
        lr = QRectF(x0 - 6, y, x1 - x0 + 12, n * APP_ROW)
        if not rows:
            ui.text(QRectF(x0, y, 400, APP_ROW), "Aucune application ne joue de son", font(8.5), T.text3)
        else:
            def draw(y0):
                yy = y0
                for item in rows:
                    rr = QRectF(lr.left(), yy, lr.width() - 8, APP_ROW - 2)
                    if self.picker:
                        dev_id, name = item
                        cur = dev_id == isl.out_id
                        if cur or ui.row_hover(rr):
                            ui.rect(rr, T.layer2 if cur else T.hover, 4)
                        if cur:
                            ui.rect(QRectF(rr.left(), rr.top() + 8, 3, rr.height() - 16), T.accent, 1.5)
                        ui.text(QRectF(rr.left() + 14, yy, rr.width() - 50, APP_ROW), name, font(8.5),
                                T.text if cur else T.text2)
                        if cur:
                            ui.glyph(QPointF(rr.right() - 16, rr.center().y()), G["check"], 11, T.accent)
                        ui.row_hit(rr, lambda d=dev_id: self.choose_output(d))
                    else:
                        app = item
                        ui.text(QRectF(rr.left() + 8, yy, 130, APP_ROW), app["name"], font(8.5),
                                T.text if not app["muted"] else T.text3)
                        ui.slider(QRectF(rr.left() + 150, yy + 5, rr.width() - 150 - 50, 20),
                                  0 if app["muted"] else app["volume"], lambda v, a=app: S.Audio.set_app_volume(a, v))
                        ui.icon_button(QPointF(rr.right() - 16, rr.center().y()), G["mute"] if app["muted"] else G["vol"],
                                       lambda a=app: S.Audio.toggle_app_mute(a), 11, None, 24)
                    yy += APP_ROW
                return yy - y0
            ui.scroll("ctl_list", lr, draw)
        y += n * APP_ROW + 8

        # ligne d'état
        x = x0
        for label, on in (("Verr. Maj", isl.caps), ("Verr. Num", isl.num)):
            f = font(7.5, W.DemiBold)
            w = ui.tw(label, f) + 26
            rr = QRectF(x, y, w, 24)
            ui.rect(rr, T.layer, 4, T.stroke)
            ui.p.setPen(T.success if on else T.track)
            ui.p.setBrush(T.success if on else T.layer)
            ui.p.drawEllipse(QPointF(rr.left() + 11, rr.center().y()), 3.5, 3.5)
            ui.text(rr.adjusted(19, 0, 0, 0), label, f, T.text if on else T.text2)
            x += w + 6
        if isl.battery:
            pct, plugged = isl.battery
            lbl = f"{pct} %" + (" · en charge" if plugged else "")
            f = font(7.5, W.DemiBold)
            w = ui.tw(lbl, f) + 30
            rr = QRectF(x, y, w, 24)
            ui.rect(rr, T.layer, 4, T.stroke)
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), G["charging"] if plugged else G["battery"], 12,
                     T.success if plugged else T.text2)
            ui.text(rr.adjusted(22, 0, 0, 0), lbl, f, T.text)
            x += w + 6
        ui.glyph(QPointF(x + 12, y + 12), G["headphone"] if head else G["speaker"], 12, T.text2)
        ui.text(QRectF(x + 24, y, x1 - x - 24, 24), isl.audio.device_name or "Aucune sortie", font(8), T.text2)
