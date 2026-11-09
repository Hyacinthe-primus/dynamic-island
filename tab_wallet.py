"""Onglet Finances : portefeuille Binance (lecture seule)."""
import datetime as dt
import hashlib
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

from store import settings
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago

CONTENT_H = 372
BINANCE_YELLOW = QColor(240, 185, 11)
XOF_PER_EUR = 655.957


def money(v, cur="$"):
    if v is None:
        return "–"
    if cur == "FCFA":
        return f"{v:,.0f}".replace(",", " ") + " FCFA"
    if abs(v) >= 1000:
        return f"{cur}{v:,.2f}".replace(",", " ")
    if abs(v) >= 1:
        return f"{cur}{v:.2f}"
    return f"{cur}{v:.4f}"


def qty(v):
    if v >= 1000:
        return f"{v:,.2f}".replace(",", " ")
    if v >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


class WalletTab:
    key, label, glyph = "wallet", "Finances", ""

    def __init__(self, isl):
        self.isl = isl

    def height(self):
        return CONTENT_H

    @property
    def hidden(self):
        return settings.get("wallet_hide", False)

    @property
    def hide_dust(self):
        return settings.get("wallet_hide_dust", True)

    def mask(self, s):
        return "••••••" if self.hidden else s

    # ------------------------------------------------------------------ dessin
    def paint(self, ui, cr):
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top() + 2
        ui.text(QRectF(x0, y, 300, 26), "Patrimoine", font(10, W.DemiBold, True))
        bx = x1
        for g, fn, on in ((G["refresh"], self._refresh, self.isl.wallet.loading),
                          ("" if self.hidden else "", lambda: settings.set("wallet_hide", not self.hidden),
                           self.hidden)):
            ui.icon_button(QPointF(bx - 14, y + 13), g, fn, 12, T.accent if on else None, 26)
            bx -= 30
        b = self.isl.wallet
        if b.configured and b.assets and b.to_xof(b.total) is not None:
            ui.text(QRectF(x0 + 100, y, bx - x0 - 110, 26), "≈ " + self.mask(money(b.to_xof(b.total), "FCFA")),
                    font(9, W.DemiBold), T.text2, RIGHT)
        body = QRectF(cr.left() + 8, y + 32, cr.width() - 16, cr.bottom() - y - 38)
        ui.scroll("finance", body, lambda yy: self._content(ui, body, yy))

    def _refresh(self):
        self.isl.wallet.refresh()

    def _content(self, ui, body, y0):
        x0, x1 = body.left() + 8, body.right() - 14
        y = self._binance(ui, x0, x1, y0)
        return y - y0 + 6

    # ------------------------------------------------------------------ Binance
    def _binance(self, ui, x0, x1, y):
        b = self.isl.wallet
        ui.glyph(QPointF(x0 + 8, y + 11), "", 13, BINANCE_YELLOW)
        ui.text(QRectF(x0 + 22, y, 200, 22), "Binance", font(9.5, W.DemiBold))
        if b.configured:
            ui.icon_button(QPointF(x1 - 12, y + 11), G["settings"], self._forget_confirm, 11, None, 24)
        y += 28
        if not b.configured:
            return self._setup(ui, x0, x1, y)
        if b.error and not b.assets:
            ui.wrap(QRectF(x0, y, x1 - x0, 50), "Erreur Binance : " + b.error, font(8.5), T.critical, 3)
            return y + 56
        if not b.assets and b.loading:
            ui.text(QRectF(x0, y, x1 - x0, 20), "Chargement du portefeuille…", font(8.5), T.text3)
            return y + 26
        ui.text(QRectF(x0, y, 300, 34), self.mask(money(b.total, "$")), font(18, W.DemiBold, True))
        up = b.change24 >= 0
        cw = ui.tw(self.mask(money(b.total, "$")), font(18, W.DemiBold, True))
        ui.badge(x0 + cw + 10, y + 9, f"{'+' if up else ''}{b.change24:.2f} % 24 h", T.success if up else T.critical)
        sub = self.mask(money(b.to_xof(b.total), "FCFA")) + "  ·  " + self.mask(money(b.to_eur(b.total), "€")) + \
            (f"  ·  maj {ago(b.time)}" if b.time else "")
        ui.text(QRectF(x0, y + 32, 360, 16), sub, font(7.5), T.text3)
        hist = b.history
        gr = QRectF(x1 - 160, y + 4, 160, 38)
        if len(hist) > 2:
            vals = [h[1] for h in hist[-120:]]
            lo, hi = min(vals), max(vals)
            path = QPainterPath()
            for i, v in enumerate(vals):
                px = gr.left() + gr.width() * i / (len(vals) - 1)
                py = gr.bottom() - (gr.height() * (v - lo) / (hi - lo) if hi > lo else gr.height() / 2)
                path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
            ui.p.setPen(QPen(T.success if vals[-1] >= vals[0] else T.critical, 1.6))
            ui.p.setBrush(Qt.BrushStyle.NoBrush)
            ui.p.drawPath(path)
        y += 56
        sums = {"Spot": 0.0, "Financement": 0.0, "Earn": 0.0}
        for a in b.assets:
            for k, src in (("Spot", "spot"), ("Financement", "funding"), ("Earn", "earn")):
                sums[k] += a[src] * a["price"]
        x = x0
        for k, v in sums.items():
            if v <= 0:
                continue
            lbl = f"{k} {self.mask(money(v, '$'))}"
            w = ui.tw(lbl, font(7.5, W.DemiBold)) + 18
            ui.rect(QRectF(x, y, w, 22), T.layer, 4, T.stroke)
            ui.text(QRectF(x, y, w, 22), lbl, font(7.5, W.DemiBold), T.text2, CENTER)
            x += w + 6
        ui.text(QRectF(x1 - 150, y, 104, 22), "Masquer < 1 $", font(7.5), T.text2, RIGHT)
        ui.toggle(QPointF(x1 - 22, y + 11), self.hide_dust, lambda: settings.set("wallet_hide_dust", not self.hide_dust))
        y += 30
        assets = [a for a in b.assets if not (self.hide_dust and a["value"] < 1)]
        for a in assets:
            rr = QRectF(x0, y, x1 - x0, 42)
            if ui.visible(rr):
                if ui.row_hover(rr):
                    ui.rect(rr, T.hover, 6)
                hsh = int(hashlib.md5(a["asset"].encode()).hexdigest()[:6], 16)
                c = BINANCE_YELLOW if a["asset"] == "BNB" else QColor.fromHsv(hsh % 360, 150, 230)
                cc = QPointF(rr.left() + 20, rr.center().y())
                ui.p.setPen(Qt.PenStyle.NoPen)
                ui.p.setBrush(T.tint(c, 60))
                ui.p.drawEllipse(cc, 14, 14)
                ui.text(QRectF(cc.x() - 14, cc.y() - 14, 28, 28), a["asset"][:4], font(6.5, W.Bold), c, CENTER)
                ui.text(QRectF(rr.left() + 42, rr.top() + 3, 150, 18), a["asset"], font(9, W.DemiBold))
                ui.text(QRectF(rr.left() + 42, rr.top() + 21, 170, 16), self.mask(qty(a["amount"])), font(7.5), T.text3)
                up_ = a["change"] >= 0
                ui.text(QRectF(rr.left() + 200, rr.top() + 3, 120, 18), money(a["price"], "$"), font(8.5), T.text2)
                if a["asset"] not in ("USDT", "USDC", "FDUSD"):
                    ui.text(QRectF(rr.left() + 200, rr.top() + 21, 120, 16), f"{'+' if up_ else ''}{a['change']:.2f} %",
                            font(7.5, W.DemiBold), T.success if up_ else T.critical)
                ui.text(QRectF(rr.right() - 140, rr.top() + 3, 132, 18), self.mask(money(a["value"], "$")),
                        font(9, W.DemiBold), T.text, RIGHT)
                share = a["value"] / b.total if b.total else 0
                ui.bar(QRectF(rr.right() - 100, rr.top() + 27, 92, 3), share, c)
                ui.text(QRectF(rr.right() - 160, rr.top() + 21, 56, 16), f"{share * 100:.1f} %", font(7), T.text3, RIGHT)
            y += 44
        if not assets:
            ui.text(QRectF(x0, y, x1 - x0, 20), "Aucun actif (ou uniquement des poussières)", font(8.5), T.text3)
            y += 24
        return y

    def _forget_confirm(self):
        t = getattr(self, "_forget_t", 0)
        if time.time() - t < 3:
            self.isl.wallet.forget()
            self.isl.fields.pop("bn_key", None)
        else:
            self._forget_t = time.time()
            self.isl.show_alert("wallet", "Déconnecter Binance ?", "Cliquez à nouveau sur Réglages pour oublier la clé",
                                T.caution, G["settings"])

    def _setup(self, ui, x0, x1, y):
        b = self.isl.wallet
        steps = ["1. Binance › Profil › Gestion des API › Créer une API (« générée par le système »).",
                 "2. Laissez UNIQUEMENT « Activer la lecture » (aucun trading, aucun retrait).",
                 "3. Collez la clé API puis la clé secrète ci-dessous (Ctrl+V puis Entrée)."]
        for s in steps:
            ui.wrap(QRectF(x0, y, x1 - x0, 34), s, font(8.5), T.text2, 2)
            y += 22
        y += 4
        has_key = bool(settings.get("binance", {}).get("key"))
        ui.field(QRectF(x0, y, x1 - x0, 30), "bn_key",
                 "Clé API enregistrée — collez-en une autre pour la remplacer" if has_key else "Clé API (API Key)",
                 on_submit=lambda t: b.set_key(t) or True, glyph="")
        y += 36
        ui.field(QRectF(x0, y, x1 - x0, 30), "bn_secret", "Clé secrète (Secret Key)",
                 on_submit=lambda t: b.set_secret(t) or True, glyph=G["lock"], secret=True)
        y += 38
        ui.button(QRectF(x0, y, 210, 28), "Ouvrir la gestion des API", lambda: self.isl.open_url(
            "https://www.binance.com/fr/my/settings/api-management"), G["open"], accent=True)
        if b.error:
            ui.text(QRectF(x0 + 220, y, x1 - x0 - 220, 28), b.error, font(8), T.critical)
        return y + 36
