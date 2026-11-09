"""Onglet Téléphone : QR de connexion, état du téléphone, envoi de texte / fichiers,
synchronisation du presse-papiers, notifications et appels (Lien avec Windows)."""
import datetime as dt
import os

from PySide6.QtCore import QPointF, QRectF

from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago

CONTENT_H = 372


class PhoneTab:
    key, label, glyph = "phone", "Téléphone", G["phone"]

    def __init__(self, isl):
        self.isl = isl
        self.show_wifi = False
        self._wifi = None

    def height(self):
        return CONTENT_H

    def toggle_wifi(self):
        self.show_wifi = not self.show_wifi
        if self.show_wifi and self._wifi is None:
            from phone import wifi_qr
            self._wifi = wifi_qr() or False

    def paint(self, ui, cr):
        isl = self.isl
        ph = isl.phone
        ph.check_network()
        x0 = cr.left() + 16
        # ---------------- colonne QR
        qc = QRectF(x0, cr.top() + 2, 196, cr.height() - 12)
        ui.card(qc)
        qr_r = QRectF(qc.left() + 18, qc.top() + 34, 160, 160)
        if self.show_wifi:
            ui.text(QRectF(qc.left() + 12, qc.top() + 6, qc.width() - 24, 24), "Wi-Fi", font(9.5, W.DemiBold))
            if self._wifi:
                ssid, txt = self._wifi
                ui.qr(qr_r, txt)
                ui.text(QRectF(qc.left() + 8, qr_r.bottom() + 6, qc.width() - 16, 18), ssid, font(8.5, W.DemiBold),
                        T.text, CENTER)
                ui.text(QRectF(qc.left() + 8, qr_r.bottom() + 24, qc.width() - 16, 16),
                        "Scannez pour rejoindre ce réseau", font(7.5), T.text3, CENTER)
            else:
                ui.empty(qr_r, G["wifi"], "Wi-Fi introuvable")
        elif ph.running:
            ui.text(QRectF(qc.left() + 12, qc.top() + 6, qc.width() - 24, 24), "Connecter un téléphone",
                    font(9.5, W.DemiBold))
            ui.qr(qr_r, ph.url)
            ui.text(QRectF(qc.left() + 8, qr_r.bottom() + 6, qc.width() - 16, 16), f"{ph.ip}:{8765}",
                    font(8, W.DemiBold), T.text2, CENTER)
            ui.wrap(QRectF(qc.left() + 12, qr_r.bottom() + 24, qc.width() - 24, 34),
                    "Même Wi-Fi. Au 1er accès : « Avancé › Continuer ».", font(7.5), T.text3, 2)
        else:
            ui.text(QRectF(qc.left() + 12, qc.top() + 6, qc.width() - 24, 24), "Connexion locale", font(9.5, W.DemiBold))
            ui.empty(qr_r, G["phone"], "Désactivée", "Fichiers, texte, télécommande")
            ui.button(QRectF(qc.left() + 18, qr_r.bottom() + 8, 160, 30), "Activer", ph.start, G["play"], accent=True)
        by = qc.bottom() - 36
        if ph.running and not self.show_wifi:
            ui.button(QRectF(qc.left() + 10, by, 84, 28), "Arrêter", ph.stop, G["stop"])
            ui.button(QRectF(qc.left() + 100, by, 86, 28), "Nouveau lien", ph.new_token, G["refresh"])
        ui.icon_button(QPointF(qc.right() - 18, qc.top() + 17), G["wifi"] if not self.show_wifi else G["phone"],
                       self.toggle_wifi, 12, T.accent if self.show_wifi else None, 26)

        # ---------------- colonne droite
        rx = qc.right() + 12
        rw = cr.right() - 16 - rx
        y = cr.top() + 2
        r = QRectF(rx, y, rw, 52)
        ui.card(r)
        dev = ph.device
        if dev:
            on = ph.connected
            ui.glyph(QPointF(r.left() + 20, r.center().y()), G["phone"], 16, T.success if on else T.text3)
            ui.text(QRectF(r.left() + 40, r.top() + 6, rw - 150, 20), dev["model"], font(9.5, W.DemiBold))
            ui.text(QRectF(r.left() + 40, r.top() + 26, rw - 150, 18),
                    "Connecté" if on else "Vu " + ago(dev["seen"]), font(7.5), T.success if on else T.text3)
            if dev.get("battery") is not None:
                b = dev["battery"]
                col = T.success if dev.get("charging") else (T.critical if b <= 20 else T.text)
                ui.text(QRectF(r.right() - 110, r.top(), 70, 52), f"{b} %", font(12, W.DemiBold, True), col, RIGHT)
                ui.glyph(QPointF(r.right() - 24, r.center().y()), G["charging"] if dev.get("charging") else G["battery"],
                         17, col)
        else:
            ui.glyph(QPointF(r.left() + 20, r.center().y()), G["phone"], 16, T.text3)
            ui.text(QRectF(r.left() + 40, r.top(), rw - 50, 52),
                    "Aucun téléphone connecté — scannez le QR code" if ph.running else "Activez la connexion locale",
                    font(8.5), T.text2)
        y += 60
        ui.field(QRectF(rx, y, rw - 36, 30), "phone_send", "Envoyer du texte au téléphone (Entrée)",
                 on_submit=lambda t: ph.push_text(t), glyph="")
        ui.icon_button(QPointF(rx + rw - 15, y + 15), G["clip"], self._send_clip, 12, None, 30)
        y += 38
        ui.text(QRectF(rx, y, rw - 60, 24), "Synchroniser le presse-papiers vers le téléphone", font(8), T.text2)
        ui.toggle(QPointF(rx + rw - 22, y + 12), ph.sync_clip, lambda: ph.set_sync_clip(not ph.sync_clip))
        y += 30
        n_files = len([p for p in isl.files.shelf if os.path.isfile(p)])
        ui.text(QRectF(rx, y, rw - 110, 20), f"{n_files} fichier(s) de l'étagère disponibles sur le téléphone",
                font(7.5), T.text3)
        ui.link(QRectF(rx + rw - 100, y, 100, 20), "Étagère ›", lambda: isl.set_tab("files"), font(7.5, W.Medium))
        y += 26
        # notifications
        ui.text(QRectF(rx, y, rw, 18), "Notifications du téléphone", font(8.5, W.DemiBold))
        y += 22
        lr = QRectF(rx - 4, y, rw + 8, cr.bottom() - y - 10)
        notes = ph.notifications
        if ph.notif_ok is False:
            ui.wrap(QRectF(rx, y, rw, 50), "Autorisez l'accès aux notifications : Paramètres › Confidentialité › "
                                           "Notifications.", font(8), T.text3, 3)
            return
        if not notes:
            ui.wrap(QRectF(rx, y, rw, 60), "Via « Lien avec Windows » : notifications et appels du téléphone "
                                           "apparaissent ici et dans l'île.", font(8), T.text3, 3)
            ui.button(QRectF(rx, y + 44, 170, 26), "Ouvrir Lien avec Windows", self._open_link, G["open"])
            return

        def draw(y0):
            yy = y0
            for n in notes:
                rr = QRectF(lr.left() + 4, yy, lr.width() - 14, 44)
                if ui.visible(rr):
                    ui.card(rr)
                    ui.glyph(QPointF(rr.left() + 16, rr.top() + 16), G["phone"] if n["call"] else G["bell"], 11,
                             T.success if n["call"] else T.accent)
                    ui.text(QRectF(rr.left() + 32, rr.top() + 4, rr.width() - 90, 18), n["title"], font(8.5, W.DemiBold))
                    ui.text(QRectF(rr.right() - 60, rr.top() + 4, 52, 18),
                            dt.datetime.fromtimestamp(n["ts"]).strftime("%H:%M"), font(7.5), T.text3, RIGHT)
                    ui.text(QRectF(rr.left() + 32, rr.top() + 22, rr.width() - 40, 18), n["body"], font(8), T.text2)
                yy += 48
            return yy - y0
        ui.scroll("phone_notifs", lr, draw)

    def _send_clip(self):
        from PySide6.QtWidgets import QApplication
        t = QApplication.clipboard().text()
        if self.isl.phone.push_text(t, "clip"):
            self.isl.show_alert("phone", "Envoyé au téléphone", t[:60], T.accent, G["phone"], duration=1.6)

    def _open_link(self):
        import subprocess
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App"])
