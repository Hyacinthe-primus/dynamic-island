"""Onglet Infos : widgets personnalisables (météo, heure mondiale, statistiques, citation,
actualités, bourse, photo, calendrier)."""
import datetime as dt
import os
import time

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPen, QPixmap

import icons
import nlp
from infos import WIDGETS, WMO, quote_of_day
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, fmt_minutes

CONTENT_H = 372


class InfosTab:
    key, label, glyph = "infos", "Infos", G["info"]

    def __init__(self, isl):
        self.isl = isl
        self.editing = False
        self.photo = None
        isl.infos.photo_ready.connect(self._photo)

    def _photo(self, img):
        self.photo = QPixmap.fromImage(img)

    def height(self):
        return CONTENT_H

    def paint(self, ui, cr):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        ui.text(QRectF(x0, cr.top(), 300, 28), "Personnaliser les widgets" if self.editing else "Widgets",
                font(10.5, W.DemiBold))
        ui.button(QRectF(x1 - 96, cr.top() + 1, 96, 26), "Terminé" if self.editing else "Modifier",
                  lambda: setattr(self, "editing", not self.editing), G["check"] if self.editing else G["settings"],
                  accent=self.editing)
        ui.icon_button(QPointF(x1 - 116, cr.top() + 14), G["refresh"], isl.infos.refresh, 12)
        body = QRectF(cr.left() + 8, cr.top() + 34, cr.width() - 16, cr.height() - 40)
        if self.editing:
            ui.scroll("infos_edit", body, lambda y: self._edit(ui, body, y))
        else:
            ui.scroll("infos", body, lambda y: self._widgets(ui, body, y))

    # ------------------------------------------------------------------ widgets
    def _widgets(self, ui, body, y0):
        y = y0
        x0, w = body.left() + 8, body.width() - 22
        for key in self.isl.infos.widgets:
            fn = getattr(self, "w_" + key, None)
            if fn:
                h = fn(ui, QRectF(x0, y, w, 0))
                y += h + 8
        return y - y0

    def _card(self, ui, r, title, g):
        if ui.visible(r):
            ui.card(r)
            ui.glyph(QPointF(r.left() + 16, r.top() + 15), g, 11, T.text2)
            ui.text(QRectF(r.left() + 30, r.top() + 5, r.width() - 40, 20), title, font(8, W.DemiBold), T.text2)

    def w_weather(self, ui, r):
        inf = self.isl.infos
        w = inf.weather
        r = QRectF(r.left(), r.top(), r.width(), 214 if w else 60)
        self._card(ui, r, "Météo" + (f" · {w['city']}" if w else ""), G["cloud"])
        if not ui.visible(r):
            return r.height()
        if not w:
            ui.text(QRectF(r.left() + 16, r.top() + 28, r.width() - 32, 20), inf.weather_err or "Chargement…",
                    font(8.5), T.text3)
            return r.height()
        label = WMO.get(w["code"], ("—", ""))[0]
        icons.weather(ui.p, QRectF(r.left() + 10, r.top() + 24, 58, 58), w["code"], w.get("is_day", True))
        ui.text(QRectF(r.left() + 72, r.top() + 24, 120, 40), f"{w['temp']:.0f}°", font(24, W.DemiBold, True))
        ui.text(QRectF(r.left() + 74, r.top() + 62, 200, 16), label, font(8.5), T.text2)
        info = [("Ressenti", f"{w['feels']:.0f}°"), ("Humidité", f"{w['hum']} %"),
                ("Vent", f"{w['wind']:.0f} km/h"), ("Pluie", f"{w['rain_now'] if w['rain_now'] is not None else '–'} %")]
        for i, (k, v) in enumerate(info):
            cx = r.left() + 210 + (i % 2) * 130
            cy = r.top() + 30 + (i // 2) * 24
            ui.text(QRectF(cx, cy, 70, 20), k, font(8), T.text3)
            ui.text(QRectF(cx + 60, cy, 64, 20), v, font(8.5, W.DemiBold), T.text, RIGHT)
        # heure par heure
        hy = r.top() + 86
        hw = (r.width() - 24) / 8
        for i, h in enumerate(w["hourly"][:8]):
            cx = r.left() + 12 + i * hw
            ui.text(QRectF(cx, hy, hw, 14), "Maint." if i == 0 else h["t"], font(7), T.text3, CENTER)
            icons.weather(ui.p, QRectF(cx, hy + 12, hw, 22), h["code"], h.get("day", True))
            ui.text(QRectF(cx, hy + 33, hw, 14), f"{h['temp']:.0f}°", font(8, W.DemiBold), T.text, CENTER)
            ui.text(QRectF(cx, hy + 46, hw, 12), f"{h['rain']} %", font(6.5), T.accent, CENTER)
        # jours
        dy = r.top() + 152
        ui.rect(QRectF(r.left() + 12, dy - 4, r.width() - 24, 1), T.stroke, 0)
        dw = (r.width() - 24) / 5
        for i, d in enumerate(w["daily"][1:6]):
            cx = r.left() + 12 + i * dw
            ui.text(QRectF(cx, dy + 2, dw, 16), nlp.JOURS[d["date"].weekday()][:3].capitalize(), font(7.5, W.DemiBold),
                    T.text2, CENTER)
            icons.weather(ui.p, QRectF(cx, dy + 17, 26, 24), d["code"], True)
            ui.text(QRectF(cx + 24, dy + 18, dw - 24, 22), f"{d['max']:.0f}° / {d['min']:.0f}°", font(8, W.DemiBold),
                    T.text)
            ui.text(QRectF(cx, dy + 40, dw, 14), f"pluie {d['rain']} %", font(6.5), T.accent, CENTER)
        return r.height()

    def w_clocks(self, ui, r):
        times = self.isl.infos.world_times()
        r = QRectF(r.left(), r.top(), r.width(), 86)
        self._card(ui, r, "Heure mondiale", G["globe"])
        if not ui.visible(r):
            return r.height()
        n = max(1, len(times))
        cw = (r.width() - 24) / n
        for i, (label, t, diff, day) in enumerate(times):
            cx = r.left() + 12 + i * cw
            ui.text(QRectF(cx, r.top() + 26, cw - 6, 16), label, font(8, W.Medium), T.text2)
            ui.text(QRectF(cx, r.top() + 40, cw - 6, 26), t.strftime("%H:%M"), font(15, W.DemiBold, True))
            sign = "+" if diff >= 0 else "−"
            dtxt = "Même heure" if diff == 0 else f"{sign}{abs(diff):g} h"
            ui.text(QRectF(cx, r.top() + 64, cw - 6, 16), dtxt + day, font(7), T.text3)
        return r.height()

    def w_stats(self, ui, r):
        isl = self.isl
        st = isl.timers.stats()
        todo, done = isl.tasks.today_counts()
        today0 = time.mktime(dt.date.today().timetuple())
        clips = sum(1 for c in isl.clip.items if c["time"] >= today0)
        evs = len([o for o in isl.agenda.day(dt.date.today())])
        up = time.time() - psutil.boot_time()
        items = [("Concentration", fmt_minutes(st["today"]), G["focus"]),
                 ("Tâches faites", f"{done} / sem. {isl.tasks.done_this_week()}", G["check"]),
                 ("Événements", str(evs), G["calendar"]),
                 ("Copies", str(clips), G["clip"]),
                 ("PC allumé depuis", fmt_minutes(up // 60), G["power"]),
                 ("Série focus", f"{st['streak']} j", G["flag"])]
        r = QRectF(r.left(), r.top(), r.width(), 124)
        self._card(ui, r, "Statistiques personnelles", G["chart"])
        if not ui.visible(r):
            return r.height()
        cw = (r.width() - 24) / 3
        for i, (k, v, g) in enumerate(items):
            cx = r.left() + 12 + (i % 3) * cw
            cy = r.top() + 30 + (i // 3) * 46
            ui.glyph(QPointF(cx + 10, cy + 12), g, 12, T.accent)
            ui.text(QRectF(cx + 26, cy, cw - 28, 16), k, font(7.5), T.text3)
            ui.text(QRectF(cx + 26, cy + 15, cw - 28, 22), v, font(10, W.DemiBold, True))
        return r.height()

    def w_quote(self, ui, r):
        q, a = quote_of_day()
        r = QRectF(r.left(), r.top(), r.width(), 92)
        self._card(ui, r, "Citation du jour", G["quote"])
        if ui.visible(r):
            ui.wrap(QRectF(r.left() + 16, r.top() + 28, r.width() - 32, 40), f"« {q} »", font(9.5), T.text, 2)
            ui.text(QRectF(r.left() + 16, r.top() + 68, r.width() - 32, 16), "— " + a, font(8), T.text2, RIGHT)
        return r.height()

    def w_news(self, ui, r):
        news = self.isl.infos.news[:6]
        r = QRectF(r.left(), r.top(), r.width(), 34 + max(1, len(news)) * 30)
        self._card(ui, r, "Actualités", G["news"])
        if not news:
            ui.text(QRectF(r.left() + 16, r.top() + 30, r.width() - 32, 20), "Chargement des flux…", font(8.5), T.text3)
            return r.height()
        y = r.top() + 30
        for n in news:
            rr = QRectF(r.left() + 6, y, r.width() - 12, 28)
            if ui.row_hover(rr):
                ui.rect(rr, T.hover, 4)
            ui.text(QRectF(rr.left() + 10, y, 90, 28), n["source"], font(7, W.DemiBold), T.accent)
            ui.text(QRectF(rr.left() + 104, y, rr.width() - 112, 28), n["title"], font(8.5))
            ui.row_hit(rr, lambda u=n["link"]: self.isl.open_url(u))
            y += 30
        return r.height()

    def w_stocks(self, ui, r):
        inf = self.isl.infos
        syms = [s for s in inf.symbols if s in inf.stocks]
        r = QRectF(r.left(), r.top(), r.width(), 34 + max(1, len(syms)) * 30)
        self._card(ui, r, "Bourse", G["chart"])
        if not syms:
            ui.text(QRectF(r.left() + 16, r.top() + 30, r.width() - 32, 20), "Chargement des cours…", font(8.5), T.text3)
            return r.height()
        y = r.top() + 30
        p = ui.p
        for s in syms:
            d = inf.stocks[s]
            up = d["change"] >= 0
            col = T.success if up else T.critical
            ui.text(QRectF(r.left() + 16, y, 80, 28), s, font(8.5, W.DemiBold))
            ui.text(QRectF(r.left() + 96, y, 140, 28), d["name"], font(7.5), T.text3)
            sp = d.get("spark") or []
            if len(sp) > 2 and ui.visible(QRectF(r.left(), y, r.width(), 28)):
                sx, sw, sy, sh = r.left() + 240, 90, y + 5, 18
                lo, hi = min(sp), max(sp)
                path = QPainterPath()
                for i, v in enumerate(sp):
                    px = sx + sw * i / (len(sp) - 1)
                    py = sy + sh - (sh * (v - lo) / (hi - lo) if hi > lo else sh / 2)
                    path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
                p.setPen(QPen(col, 1.4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            price = d["price"]
            ptxt = f"{price:,.2f}".replace(",", " ") if price else "–"
            ui.text(QRectF(r.right() - 170, y, 100, 28), f"{ptxt} {d['cur']}", font(8.5, W.DemiBold), T.text, RIGHT)
            ui.text(QRectF(r.right() - 64, y, 50, 28), f"{'+' if up else ''}{d['change']:.2f}%", font(8, W.DemiBold), col, RIGHT)
            y += 30
        return r.height()

    def w_photo(self, ui, r):
        r = QRectF(r.left(), r.top(), r.width(), 170)
        self._card(ui, r, "Photo favorite", G["photo"])
        if not ui.visible(r):
            return r.height()
        ir = QRectF(r.left() + 8, r.top() + 28, r.width() - 16, r.height() - 36)
        if self.photo:
            clip = QPainterPath()
            clip.addRoundedRect(ir, 4, 4)
            ui.p.save()
            ui.p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
            pm = self.photo
            sx = max(0, (pm.width() - ir.width()) / 2)
            sy = max(0, (pm.height() - ir.height()) / 2)
            ui.p.drawPixmap(ir, pm, QRectF(sx, sy, min(pm.width(), ir.width()), min(pm.height(), ir.height())))
            ui.p.restore()
            path = self.isl.infos.photo_path
            if path:
                ui.row_hit(ir, lambda: os.startfile(path))
        else:
            ui.text(ir, "Aucune photo trouvée — choisissez un dossier dans « Modifier »", font(8.5), T.text3, CENTER)
        return r.height()

    def w_calendar(self, ui, r):
        r = QRectF(r.left(), r.top(), r.width(), 196)
        self._card(ui, r, "Calendrier", G["calendar"])
        if ui.visible(r):
            ag = self.isl.tabs["agenda"]
            today = dt.date.today()
            ui.text(QRectF(r.left() + 16, r.top() + 26, 200, 18), f"{nlp.MOIS[today.month - 1].capitalize()} {today.year}",
                    font(9, W.DemiBold))
            ag.month_grid(ui, QRectF(r.left() + 12, r.top() + 46, r.width() - 24, 144), today.replace(day=1), None,
                          lambda d: (ag._open_day(d), self.isl.set_tab("agenda")), mini=True)
        return r.height()

    # ------------------------------------------------------------------ édition
    def _edit(self, ui, body, y0):
        isl = self.isl
        inf = isl.infos
        x0, x1 = body.left() + 8, body.right() - 14
        y = y0
        ui.text(QRectF(x0, y, 300, 18), "Widgets affichés (ordre modifiable)", font(8.5, W.DemiBold))
        y += 24
        enabled = list(inf.widgets)
        order = enabled + [k for k, _ in WIDGETS if k not in enabled]
        names = dict(WIDGETS)
        for i, k in enumerate(order):
            r = QRectF(x0, y, x1 - x0, 32)
            ui.card(r)
            on = k in enabled
            ui.text(QRectF(r.left() + 14, r.top(), 200, 32), names[k], font(9), T.text if on else T.text3)
            if on:
                idx = enabled.index(k)
                ui.icon_button(QPointF(r.right() - 120, r.center().y()), G["up"],
                               lambda idx=idx: self._move(idx, -1), 10, size=24)
                ui.icon_button(QPointF(r.right() - 94, r.center().y()), G["down"],
                               lambda idx=idx: self._move(idx, 1), 10, size=24)
            ui.toggle(QPointF(r.right() - 34, r.center().y()), on, lambda k=k: self._toggle(k))
            y += 36
        y += 8
        loc = inf.location or {}
        for name, label, ph, fn in (
            ("cfg_city", f"Ville de la météo : {loc.get('name', 'auto')}", "Changer de ville (Entrée)",
             lambda t: inf.set_city(t) or True),
            ("cfg_clocks", "Heure mondiale : " + ", ".join(c[0] for c in inf.clocks),
             "Villes séparées par des virgules : Lomé, Paris, Montréal", lambda t: inf.set_clocks_text(t)),
            ("cfg_stocks", "Bourse : " + ", ".join(inf.symbols), "Symboles Yahoo : AAPL, MSFT, BTC-USD, ^FCHI",
             lambda t: inf.set_symbols_text(t) or True),
            ("cfg_feed", f"Actualités : {len(inf.feeds)} flux RSS", "Ajouter un flux RSS (https://…)",
             lambda t: inf.add_feed(t.strip()) or True),
        ):
            ui.text(QRectF(x0, y, x1 - x0, 18), label, font(8, W.Medium), T.text2)
            ui.field(QRectF(x0, y + 20, x1 - x0, 30), name, ph, on_submit=fn)
            y += 58
        from store import settings
        ui.text(QRectF(x0, y, x1 - x0 - 150, 26), "Photos : " + (settings.get("photo_dir") or "Images"), font(8, W.Medium), T.text2)
        ui.button(QRectF(x1 - 140, y, 140, 26), "Choisir un dossier…", self._pick_photos, G["folder"])
        y += 34
        return y - y0

    def _move(self, idx, d):
        lst = list(self.isl.infos.widgets)
        j = idx + d
        if 0 <= j < len(lst):
            lst[idx], lst[j] = lst[j], lst[idx]
            self.isl.infos.set_widgets(lst)

    def _toggle(self, k):
        lst = list(self.isl.infos.widgets)
        if k in lst:
            lst.remove(k)
        else:
            lst.append(k)
        self.isl.infos.set_widgets(lst)

    def _pick_photos(self):
        from PySide6.QtWidgets import QFileDialog
        self.isl.close_island(restore_focus=False)
        d = QFileDialog.getExistingDirectory(None, "Dossier de photos favorites", os.path.expanduser("~"))
        if d:
            self.isl.infos.set_photo_dir(d)
