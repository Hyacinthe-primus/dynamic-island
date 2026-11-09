"""Onglet Accueil : heure, date, météo, média, prochain événement, tâches du jour, minuteurs."""
import datetime as dt
import time

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

import icons
import nlp
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, fmt_dur, until

CONTENT_H = 372


class HomeTab:
    key, label, glyph = "home", "Accueil", G["home"]

    def __init__(self, isl):
        self.isl = isl

    def height(self):
        return CONTENT_H

    def paint(self, ui, cr):
        isl = self.isl
        now = dt.datetime.now()
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top() + 4

        # heure + date
        ui.text(QRectF(x0, y, 200, 46), now.strftime("%H:%M"), font(28, W.Light, True), T.text)
        date = f"{nlp.JOURS[now.weekday()]} {now.day} {nlp.MOIS[now.month - 1]} {now.year}"
        ui.text(QRectF(x0 + 2, y + 46, 260, 18), date.capitalize(), font(9), T.text2)

        # météo
        w = isl.infos.weather
        if w:
            from infos import WMO
            label = WMO.get(w["code"], ("—", ""))[0]
            icons.weather(ui.p, QRectF(x1 - 214, y, 50, 50), w["code"], w.get("is_day", True))
            ui.text(QRectF(x1 - 160, y + 2, 160, 28), f"{w['temp']:.0f}°", font(18, W.DemiBold, True), T.text, RIGHT)
            sub = f"{label} · {w['city']}"
            ui.text(QRectF(x1 - 260, y + 32, 260, 16), sub, font(8), T.text2, RIGHT)
            if w.get("rain_now") is not None:
                ui.text(QRectF(x1 - 260, y + 48, 260, 16), f"Pluie {w['rain_now']} %  ·  ressenti {w['feels']:.0f}°",
                        font(8), T.text3, RIGHT)
            ui.hit(QRectF(x1 - 260, y, 260, 64), lambda: isl.set_tab("infos"))
        elif isl.infos.weather_err:
            ui.text(QRectF(x1 - 260, y + 10, 260, 18), isl.infos.weather_err, font(8), T.text3, RIGHT)

        y += 72
        ui.scroll("home", QRectF(cr.left() + 8, y, cr.width() - 16, cr.bottom() - y - 8),
                  lambda yy: self._body(ui, cr, yy))

    # ------------------------------------------------------------------
    def _body(self, ui, cr, y0):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = y0

        # média
        m = isl.media
        if m:
            card = QRectF(x0 - 4, y, x1 - x0 + 8, 74)
            ui.card(card)
            art = QRectF(card.left() + 10, card.top() + 10, 54, 54)
            isl.draw_art(ui.p, art, 6)
            tx = card.left() + 76
            tw = card.width() - 76 - 176
            info = QRectF(art.left(), card.top() + 4, tx + tw - art.left(), 44)
            if ui.row_hover(info):  # clic sur la pochette ou le titre = ouvrir l'application
                ui.rect(art, QColor(0, 0, 0, 120), 6)
                ui.glyph(art.center(), G["open"], 16, T.text)
            ui.hit(info, isl.open_media_app)
            ui.text(QRectF(tx, card.top() + 12, tw, 18), m["title"], font(9.5, W.DemiBold))
            sub = " · ".join(x for x in (m["artist"], m["app"]) if x)
            ui.text(QRectF(tx, card.top() + 31, tw, 16), sub, font(8.5), T.text2)
            if m["duration"] > 0:
                ui.bar(QRectF(tx, card.top() + 54, tw, 3), isl.media_position() / m["duration"])
            # bouton : icône réelle de l'application qui joue
            ab = QRectF(card.right() - 172, card.center().y() - 17, 34, 34)
            if ui.hovering(ab):
                ui.rect(ab, T.hover, 4)
            if isl.media_exe:
                ui.file_icon(ab.adjusted(8, 8, -8, -8), isl.media_exe, G["open"])
            else:
                ui.glyph(ab.center(), G["open"], 13, T.text2)
            ui.hit(ab, isl.open_media_app)
            cx, cy = card.right() - 70, card.center().y()
            ui.icon_button(QPointF(cx - 38, cy), "", lambda: isl.media_cmd("previous"), 14)
            ui.icon_button(QPointF(cx, cy), G["pause"] if m["playing"] else G["play"],
                           lambda: isl.media_cmd("play_pause"), 16, T.text, 34)
            ui.icon_button(QPointF(cx + 38, cy), "", lambda: isl.media_cmd("next"), 14)
            y += 82

        # minuteurs actifs
        act = isl.timers.active()
        if act:
            label, rem, frac, kind = act
            card = QRectF(x0 - 4, y, x1 - x0 + 8, 44)
            ui.card(card)
            col = T.success if kind == "pomo" and isl.timers.pomo["phase"] != "work" else T.accent
            if frac is not None:
                ui.ring(QPointF(card.left() + 24, card.center().y()), 11, frac, col, 3)
            else:
                ui.glyph(QPointF(card.left() + 24, card.center().y()), G["timer"], 14, col)
            ui.text(QRectF(card.left() + 46, card.top(), 200, 44), label, font(9, W.Medium))
            ui.text(QRectF(card.right() - 150, card.top(), 136, 44), fmt_dur(rem), font(14, W.DemiBold, True), T.text, RIGHT)
            ui.hit(card, lambda: isl.set_tab("timers"))
            y += 52

        # prochain événement
        ui.section(x0, y, x1 - x0, "À venir", "Agenda ›", lambda: isl.set_tab("agenda"))
        y += 22
        nxt = isl.agenda.upcoming(3, 14)
        if not nxt:
            ui.text(QRectF(x0, y, x1 - x0, 20), "Aucun événement prévu — ajoutez-en dans l'onglet Agenda", font(8.5), T.text3)
            y += 26
        for o in nxt[:2]:
            y = self._event_row(ui, x0, x1, y, o)
        bd = [b for b in isl.agenda.birthdays(30) if b not in nxt]
        if bd:
            b = bd[0]
            d = dt.date.fromtimestamp(b["start"])
            age = f" ({b['age']} ans)" if b.get("age") else ""
            icons.cake(ui.p, QRectF(x0, y, 17, 17))
            ui.text(QRectF(x0 + 22, y, x1 - x0 - 22, 18), f"{b['title']}{age} — {d.day} {nlp.MOIS[d.month - 1]}",
                    font(8.5), T.text2)
            y += 24

        # tâches du jour
        y += 6
        todo, done = isl.tasks.today_counts()
        ui.section(x0, y, x1 - x0, "Tâches du jour", f"{done}/{todo + done} faites ›", lambda: isl.set_tab("tasks"))
        y += 24
        ui.field(QRectF(x0, y, x1 - x0, 30), "home_task", "Ajouter une tâche… (ex : Appeler Paul 15h !haute)",
                 on_submit=lambda t: isl.tasks.quick_add(t) is not None, glyph=G["add"])
        y += 36
        tasks = [t for t in isl.tasks.query("today") if not t.get("done")][:4]
        if not tasks:
            ui.text(QRectF(x0, y, x1 - x0, 20), "Rien d'urgent aujourd'hui", font(8.5), T.text3)
            y += 24
        for t in tasks:
            r = QRectF(x0 - 4, y, x1 - x0 + 8, 28)
            if ui.row_hover(r):
                ui.rect(r, T.hover, 4)
            col = {3: T.critical, 2: T.orange, 1: T.accent}.get(t.get("priority", 0), T.track)
            ui.checkbox(QPointF(x0 + 8, y + 14), t.get("done"), lambda t=t: isl.tasks.toggle(t), col, round_=True)
            ui.text(QRectF(x0 + 24, y, x1 - x0 - 140, 28), t["title"], font(9))
            lbl, late = isl.tasks.due_label(t)
            if lbl:
                ui.text(QRectF(x1 - 120, y, 116, 28), lbl, font(8), T.critical if late else T.text3, RIGHT)
            y += 30
        return y - y0 + 6

    def _event_row(self, ui, x0, x1, y, o):
        isl = self.isl
        now = time.time()
        r = QRectF(x0 - 4, y, x1 - x0 + 8, 44)
        ui.card(r)
        col = T.orange if o.get("birthday") else (T.accent if o.get("local") else T.purple)
        ui.rect(QRectF(r.left() + 6, r.top() + 8, 3, 28), col, 1.5)
        d = dt.date.fromtimestamp(o["start"])
        if o["all_day"]:
            when = "Toute la journée"
        else:
            when = dt.datetime.fromtimestamp(o["start"]).strftime("%H:%M")
            when += "–" + dt.datetime.fromtimestamp(o["end"]).strftime("%H:%M")
        if d != dt.date.today():
            when = ("Demain " if d == dt.date.today() + dt.timedelta(days=1) else
                    f"{nlp.JOURS[d.weekday()][:3].capitalize()} {d.day} ") + when
        right_w = 0
        if o.get("meet_url"):
            right_w = 96
            br = QRectF(r.right() - 92, r.top() + 8, 84, 28)
            ui.button(br, "Rejoindre", lambda u=o["meet_url"]: isl.open_url(u), G["video"], accent=True)
        elif not o["all_day"] and o["start"] > now:
            right_w = 90
            ui.text(QRectF(r.right() - 96, r.top(), 86, 44), until(o["start"] - now), font(8.5, W.DemiBold), T.accent, RIGHT)
        ui.text(QRectF(r.left() + 18, r.top() + 5, r.width() - 30 - right_w, 18), o["title"], font(9, W.DemiBold))
        sub = when + (f" · {o['meet_app']}" if o.get("meet_app") else (f" · {o['location']}" if o.get("location") else ""))
        ui.text(QRectF(r.left() + 18, r.top() + 23, r.width() - 30 - right_w, 16), sub, font(8), T.text2)
        return y + 50
