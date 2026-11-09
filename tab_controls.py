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
        self.panel = None          # "wifi" | "bt" : panneau détaillé
        self.wifi_expand = None    # réseau dont on saisit le mot de passe
        self.forget = None

    def height(self):
        if self.panel:
            return 372
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

    # ------------------------------------------------------------------ panneaux Wi-Fi / Bluetooth
    def open_panel(self, which):
        self.panel = which
        self.wifi_expand = None
        self.isl.scrolls.pop("net_panel", None)
        if which == "wifi":
            self.isl.net.scan_wifi()
        else:
            self.isl.net.refresh_bt()

    def close_panel(self):
        self.panel = None
        if self.isl.focus_field == "wifi_pw":
            self.isl.unfocus(restore=False)

    def _wifi_click(self, n):
        net = self.isl.net
        if net.wifi_cur.get("ssid") == n["ssid"] or net.wifi_busy:
            return
        if n["open"] or net.known(n["ssid"]):
            net.connect_wifi(n)
        else:
            self.wifi_expand = n["ssid"]
            self.isl.fields["wifi_pw"] = ""
            self.isl.focus("wifi_pw")

    def _wifi_password(self, n, pw):
        if len(pw) < 8:
            self.isl.show_alert("wifi", "Mot de passe trop court", "8 caractères minimum (WPA2)", T.critical, G["wifi"])
            return False
        self.isl.net.connect_wifi(n, pw)
        self.wifi_expand = None
        self.isl.unfocus(restore=False)
        return True

    def _forget(self, ssid):
        if self.forget and self.forget[0] == ssid and time.time() - self.forget[1] < 3:
            self.forget = None
            self.isl.net.forget_wifi(ssid)
        else:
            self.forget = (ssid, time.time())

    @staticmethod
    def _bars(ui, c, signal, col):
        """Quatre barres de signal façon Windows."""
        n = 1 if signal < 30 else 2 if signal < 55 else 3 if signal < 80 else 4
        for i in range(4):
            h = 4 + i * 3
            ui.rect(QRectF(c.x() - 8 + i * 4.5, c.y() + 7 - h, 3, h), col if i < n else T.tint(col, 60), 1)

    def _panel(self, ui, cr):
        isl = self.isl
        net = isl.net
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top() + 4
        wifi = self.panel == "wifi"
        ui.icon_button(QPointF(x0 + 12, y + 14), G["left"], self.close_panel, 12, None, 28)
        ui.text(QRectF(x0 + 32, y, 200, 28), "Wi-Fi" if wifi else "Bluetooth", font(11, W.DemiBold, True))
        radio_on = bool(isl.wifi if wifi else isl.bt)
        busy = net.wifi_scanning if wifi else net.bt_loading
        if busy:
            ui.text(QRectF(x1 - 210, y, 110, 28), "Recherche…", font(8), T.text3, RIGHT)
        else:
            ui.icon_button(QPointF(x1 - 86, y + 14), G["refresh"],
                           net.scan_wifi if wifi else net.refresh_bt, 11, None, 26)
        ui.toggle(QPointF(x1 - 24, y + 14), radio_on,
                  lambda: isl.toggle_radio("wifi" if wifi else "bluetooth"))
        body = QRectF(cr.left() + 8, y + 36, cr.width() - 16, cr.bottom() - y - 76)
        if not radio_on:
            ui.empty(body, G["wifi"] if wifi else G["bt"], ("Wi-Fi" if wifi else "Bluetooth") + " désactivé",
                     "Activez-le avec l'interrupteur en haut à droite")
        elif wifi:
            ui.scroll("net_panel", body, lambda yy: self._wifi_list(ui, body, yy))
        else:
            ui.scroll("net_panel", body, lambda yy: self._bt_list(ui, body, yy))
        fy = cr.bottom() - 36
        if wifi:
            ui.button(QRectF(x0, fy, 170, 28), "Paramètres Wi-Fi", lambda: isl.open_url("ms-settings:network-wifi"),
                      G["settings"])
            ui.text(QRectF(x0 + 180, fy, x1 - x0 - 180, 28), "Les réseaux masqués se rejoignent depuis les paramètres",
                    font(7.5), T.text3)
        else:
            ui.button(QRectF(x0, fy, 170, 28), "Ajouter un appareil", lambda: isl.open_url("ms-settings:bluetooth"),
                      G["add"], accent=True)
            ui.text(QRectF(x0 + 180, fy, x1 - x0 - 180, 28), "Connexion / déconnexion : casques et enceintes",
                    font(7.5), T.text3)

    def _wifi_list(self, ui, body, y0):
        net = self.isl.net
        x0, x1 = body.left() + 8, body.right() - 14
        y = y0
        cur = net.wifi_cur.get("ssid")
        nets = list(net.wifi)
        if cur and not any(n["ssid"] == cur for n in nets):
            nets.insert(0, {"ssid": cur, "auth": "", "signal": net.wifi_cur.get("signal") or 0, "open": False})
        nets.sort(key=lambda n: (n["ssid"] != cur, not net.known(n["ssid"]), -n["signal"]))
        if not nets:
            ui.text(QRectF(x0, y + 10, x1 - x0, 20), "Recherche des réseaux…" if net.wifi_scanning else
                    "Aucun réseau trouvé", font(9), T.text3, CENTER)
            return 40
        for n in nets:
            ssid = n["ssid"]
            connected = ssid == cur
            expanded = self.wifi_expand == ssid
            h = 88 if expanded else 46
            r = QRectF(x0, y, x1 - x0, h)
            if ui.visible(r):
                hov = ui.row_hover(QRectF(r.left(), r.top(), r.width(), 46))
                ui.rect(r, T.layer2 if (hov or expanded or connected) else T.layer, 6, T.accent if connected else T.stroke)
                col = T.accent if connected else T.text
                self._bars(ui, QPointF(r.left() + 22, r.top() + 23), n["signal"], col)
                if not n["open"]:
                    ui.glyph(QPointF(r.left() + 30, r.top() + 31), G["lock"], 8, T.text2)
                ui.text(QRectF(r.left() + 46, r.top() + 5, r.width() - 190, 18), ssid, font(9, W.DemiBold))
                if net.wifi_busy == ssid:
                    sub, sc = "Connexion…", T.accent
                elif connected:
                    sub, sc = f"Connecté · {n['signal']} %", T.success
                elif net.known(ssid):
                    sub, sc = "Enregistré · " + ("ouvert" if n["open"] else "sécurisé"), T.text3
                else:
                    sub, sc = ("Ouvert (non sécurisé)" if n["open"] else n["auth"] or "Sécurisé"), T.text3
                ui.text(QRectF(r.left() + 46, r.top() + 24, r.width() - 190, 16), sub, font(7.5), sc)
                if connected:
                    ui.button(QRectF(r.right() - 112, r.top() + 9, 102, 28), "Déconnecter", net.disconnect_wifi)
                else:
                    ui.row_hit(QRectF(r.left(), r.top(), r.width() - (90 if hov else 0), 46),
                               lambda n=n: self._wifi_click(n))
                    if hov and not expanded and not net.wifi_busy:
                        if net.known(ssid):
                            f = self.forget and self.forget[0] == ssid and time.time() - self.forget[1] < 3
                            ui.button(QRectF(r.right() - 182, r.top() + 9, 82, 28), "Confirmer" if f else "Oublier",
                                      lambda s_=ssid: self._forget(s_), danger=True)
                        ui.button(QRectF(r.right() - 94, r.top() + 9, 84, 28), "Connecter",
                                  lambda n=n: self._wifi_click(n), accent=True)
                if expanded:
                    ui.field(QRectF(r.left() + 46, r.top() + 48, r.width() - 160, 30), "wifi_pw",
                             "Mot de passe du réseau, puis Entrée",
                             on_submit=lambda t, n=n: self._wifi_password(n, t), glyph=G["lock"], secret=True)
                    ui.button(QRectF(r.right() - 106, r.top() + 49, 96, 28), "Se connecter",
                              lambda n=n: self._wifi_password(n, self.isl.fields.get("wifi_pw", "")), accent=True)
            y += h + 6
        return y - y0

    def _bt_list(self, ui, body, y0):
        net = self.isl.net
        x0, x1 = body.left() + 8, body.right() - 14
        y = y0
        devs = net.bt
        if not devs:
            ui.text(QRectF(x0, y + 10, x1 - x0, 20), "Chargement des appareils…" if net.bt_loading else
                    "Aucun appareil appairé — utilisez « Ajouter un appareil »", font(9), T.text3, CENTER)
            return 40
        icon = {"audio": G["headphone"], "phone": G["phone"], "input": G["keyboard"], "computer": chr(0xE7F8)}
        for d in devs:
            r = QRectF(x0, y, x1 - x0, 46)
            if ui.visible(r):
                hov = ui.row_hover(r)
                conn = d["connected"]
                ui.rect(r, T.layer2 if (hov or conn) else T.layer, 6, T.accent if conn else T.stroke)
                ic = icon.get(d["kind"], G["bt"])
                ui.glyph(QPointF(r.left() + 22, r.center().y()), ic, 15, T.accent if conn else T.text2)
                ui.text(QRectF(r.left() + 46, r.top() + 5, r.width() - 180, 18), d["name"], font(9, W.DemiBold))
                if net.bt_busy == d["address"]:
                    sub, sc = ("Déconnexion…" if conn else "Connexion…"), T.accent
                elif conn:
                    sub, sc = "Connecté", T.success
                elif d.get("off"):
                    sub, sc = "Déconnecté depuis l'île", T.text3
                else:
                    sub, sc = "Appairé · non connecté", T.text3
                kind = {"audio": "Audio", "phone": "Téléphone", "input": "Clavier / souris",
                        "computer": "Ordinateur"}.get(d["kind"], "Appareil")
                ui.text(QRectF(r.left() + 46, r.top() + 24, r.width() - 180, 16), f"{sub} · {kind}", font(7.5), sc)
                if d["kind"] == "audio" and d["address"] and not net.bt_busy:
                    ui.button(QRectF(r.right() - 112, r.top() + 9, 102, 28), "Déconnecter" if conn else "Connecter",
                              lambda d=d: net.bt_toggle(d), accent=not conn)
            y += 52
        return y - y0

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
        if self.panel:
            return self._panel(ui, cr)
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top() + 4
        cols = 5
        gap = 8
        tw = (x1 - x0 - gap * (cols - 1)) / cols
        mic_on = isl.audio.mic_available() and not isl.audio.mic_muted()
        conf = self.confirm and self.confirm > time.time()
        head = isl.headphones()
        tiles = [
            (G["wifi"], (isl.net.wifi_cur.get("ssid") if isl.wifi else None) or "Wi-Fi", bool(isl.wifi),
             lambda: isl.toggle_radio("wifi"), False, isl.wifi is not None, None, lambda: self.open_panel("wifi")),
            (G["bt"], (next((d["name"] for d in isl.net.bt if d["connected"] and d["kind"] == "audio"), None)
                       if isl.bt else None) or "Bluetooth", bool(isl.bt),
             lambda: isl.toggle_radio("bluetooth"), False, isl.bt is not None, None, lambda: self.open_panel("bt")),
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
        for i, t in enumerate(tiles):
            g, label, on, fn, slash, enabled, color = t[:7]
            r = QRectF(x0 + (i % cols) * (tw + gap), y + (i // cols) * 66, tw, 62)
            ui.tile(r, g, label, on, fn, slash, enabled, color, more=t[7] if len(t) > 7 else None)
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
