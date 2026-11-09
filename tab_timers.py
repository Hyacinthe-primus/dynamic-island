"""Onglet Minuteurs : comptes à rebours multiples, Pomodoro, chronomètre, alarmes, statistiques."""
import datetime as dt
import re

from PySide6.QtCore import QPointF, QRectF

import nlp
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, fmt_dur, fmt_minutes

CONTENT_H = 372
VIEWS = [("timers", "Minuteurs"), ("pomo", "Pomodoro"), ("sw", "Chrono"), ("alarms", "Alarmes"),
         ("stats", "Statistiques")]
PRESETS = [60, 180, 300, 600, 900, 1800, 3600]
DAYS = ["L", "M", "M", "J", "V", "S", "D"]


class TimersTab:
    key, label, glyph = "timers", "Minuteurs", G["timer"]

    def __init__(self, isl):
        self.isl = isl
        self.view = "timers"

    def height(self):
        return CONTENT_H

    def set_view(self, v):
        self.view = v

    def paint(self, ui, cr):
        x0 = cr.left() + 16
        ui.segmented(QRectF(x0 - 6, cr.top(), 0, 30), VIEWS, self.view, self.set_view)
        body = QRectF(cr.left() + 16, cr.top() + 38, cr.width() - 32, cr.height() - 46)
        getattr(self, "_" + self.view)(ui, body)

    # ------------------------------------------------------------------ minuteurs
    def _add(self, text):
        m = re.match(r"\s*(\S+)\s*(.*)", text)
        if not m:
            return False
        sec = nlp.parse_duration(m.group(1))
        if not sec:
            return False
        self.isl.timers.add_timer(sec, m.group(2).strip() or None)
        return True

    def _timers(self, ui, body):
        tm = self.isl.timers
        x = body.left()
        for s in PRESETS:
            lbl = f"{s // 60} min" if s < 3600 else "1 h"
            w = ui.chip_w(lbl, G["add"])
            ui.chip(QRectF(x, body.top(), w, 24), lbl, False, lambda s=s: tm.add_timer(s), G["add"])
            x += w + 4
        ui.field(QRectF(body.left(), body.top() + 32, body.width(), 30), "timer_add",
                 "Minuteur personnalisé : « 12m thé », « 1h30 four », « 90s » (Entrée)", on_submit=self._add,
                 glyph=G["timer"])
        lr = QRectF(body.left() - 8, body.top() + 70, body.width() + 16, body.height() - 70)
        if not tm.timers:
            ui.empty(lr, G["timer"], "Aucun minuteur", "Plusieurs minuteurs peuvent tourner en même temps")
            return

        def draw(y0):
            y = y0
            for t in list(tm.timers):
                r = QRectF(lr.left() + 8, y, lr.width() - 22, 58)
                if ui.visible(r):
                    ui.card(r)
                    rem = tm.remaining(t)
                    done = rem <= 0
                    col = T.success if done else T.accent
                    ui.ring(QPointF(r.left() + 30, r.center().y()), 17, 1 - rem / max(1, t["duration"]), col, 3.5)
                    ui.glyph(QPointF(r.left() + 30, r.center().y()), G["check"] if done else
                             (G["pause"] if t["running"] else G["play"]), 11, col)
                    ui.hit(QRectF(r.left() + 10, r.top() + 9, 40, 40), lambda t=t: tm.toggle_timer(t))
                    ui.text(QRectF(r.left() + 60, r.top() + 6, 220, 26), fmt_dur(rem), font(15, W.DemiBold, True))
                    ui.text(QRectF(r.left() + 60, r.top() + 32, 220, 18),
                            t["label"] + (" · terminé" if done else ("" if t["running"] else " · en pause")),
                            font(8), T.text2)
                    bx = r.right() - 20
                    ui.icon_button(QPointF(bx, r.center().y()), G["delete"], lambda t=t: tm.remove_timer(t), 12, T.critical)
                    ui.icon_button(QPointF(bx - 32, r.center().y()), G["refresh"], lambda t=t: tm.reset_timer(t), 12)
                    ui.button(QRectF(bx - 96, r.center().y() - 13, 46, 26), "+1 min", lambda t=t: tm.add_time(t, 60))
                    ui.icon_button(QPointF(bx - 118, r.center().y()), G["pause"] if t["running"] else G["play"],
                                   lambda t=t: tm.toggle_timer(t), 13, T.text)
                y += 64
            return y - y0
        ui.scroll("timers", lr, draw)

    # ------------------------------------------------------------------ pomodoro
    def _pomo(self, ui, body):
        isl = self.isl
        tm = isl.timers
        p = tm.pomo
        c = QPointF(body.left() + 84, body.top() + 104)
        rem = tm.pomo_remaining()
        col = T.accent if p["phase"] == "work" else T.success
        ui.ring(c, 74, 1 - rem / max(1, tm.phase_len()), col, 6)
        ui.text(QRectF(c.x() - 70, c.y() - 26, 140, 40), fmt_dur(rem), font(22, W.DemiBold, True), T.text, CENTER)
        phase = {"work": "Concentration", "short": "Petite pause", "long": "Grande pause"}[p["phase"]]
        ui.text(QRectF(c.x() - 70, c.y() + 12, 140, 18), phase, font(8.5, W.Medium), col, CENTER)
        every = tm.pomo_cfg["every"]
        done_in_cycle = p["cycles"] % every
        for i in range(every):
            ui.p.setPen(col if i < done_in_cycle else T.track)
            ui.p.setBrush(col if i < done_in_cycle else T.layer)
            ui.p.drawEllipse(QPointF(c.x() + (i - (every - 1) / 2) * 12, c.y() + 40), 3.5, 3.5)
        by = body.top() + 196
        ui.button(QRectF(body.left() + 4, by, 104, 32), "Pause" if p["running"] else "Démarrer", tm.pomo_toggle,
                  G["pause"] if p["running"] else G["play"], accent=True)
        ui.icon_button(QPointF(body.left() + 128, by + 16), G["right"], tm.pomo_skip, 13, size=32)
        ui.icon_button(QPointF(body.left() + 162, by + 16), G["refresh"], tm.pomo_reset, 13, size=32)
        ui.text(QRectF(body.left(), by + 40, 190, 18), f"{p['cycles']} session(s) aujourd'hui · cycle de {every}",
                font(7.5), T.text3, CENTER)

        # réglages + concentration
        rx = body.left() + 206
        rw = body.right() - rx
        r = QRectF(rx, body.top(), rw, 64)
        ui.card(r)
        ui.glyph(QPointF(r.left() + 20, r.top() + 22), G["focus"], 15, T.accent if tm.focus else T.text2)
        ui.text(QRectF(r.left() + 38, r.top() + 10, rw - 100, 18), "Mode concentration", font(9.5, W.DemiBold))
        ui.wrap(QRectF(r.left() + 38, r.top() + 29, rw - 100, 30), "Lance un Pomodoro et active Ne pas déranger",
                font(7.5), T.text2, lines=2)
        ui.toggle(QPointF(r.right() - 32, r.top() + 22), tm.focus, lambda: isl.set_focus(not tm.focus))
        y = body.top() + 74
        ui.field(QRectF(rx, y, rw, 30), "pomo_label", p.get("label") or "Sur quoi travaillez-vous ?",
                 on_submit=lambda t: p.update(label=t.strip() or "Concentration") or True, glyph=G["edit"])
        y += 40
        for key, lbl, lo, hi, step in (("work", "Travail", 5, 90, 5), ("short", "Petite pause", 1, 30, 1),
                                       ("long", "Grande pause", 5, 60, 5), ("every", "Grande pause tous les", 2, 8, 1)):
            v = tm.pomo_cfg[key]
            ui.text(QRectF(rx, y, rw - 120, 28), lbl, font(8.5), T.text2)
            ui.icon_button(QPointF(rx + rw - 100, y + 14), "",
                           lambda k=key, v=v, lo=lo, s=step: tm.set_pomo_cfg(**{k: max(lo, v - s)}), 10, size=24)
            ui.text(QRectF(rx + rw - 86, y, 56, 28), f"{v}" + ("" if key == "every" else " min"),
                    font(9, W.DemiBold), T.text, CENTER)
            ui.icon_button(QPointF(rx + rw - 16, y + 14), G["add"],
                           lambda k=key, v=v, hi=hi, s=step: tm.set_pomo_cfg(**{k: min(hi, v + s)}), 10, size=24)
            y += 30
        ui.text(QRectF(rx, y + 2, rw - 60, 24), "Enchaîner automatiquement", font(8.5), T.text2)
        ui.toggle(QPointF(rx + rw - 22, y + 14), tm.pomo_cfg["auto"],
                  lambda: tm.set_pomo_cfg(auto=not tm.pomo_cfg["auto"]))

    # ------------------------------------------------------------------ chrono
    def _sw(self, ui, body):
        tm = self.isl.timers
        e = tm.sw_elapsed()
        cs = int((e % 1) * 100)
        ui.text(QRectF(body.left(), body.top() + 6, body.width(), 56), fmt_dur(e, e >= 3600) + f".{cs:02d}",
                font(30, W.Light, True), T.text, CENTER)
        bx = body.center().x()
        by = body.top() + 72
        ui.button(QRectF(bx - 160, by, 100, 32), "Tour", tm.sw_lap, G["flag"], enabled=tm.stopwatch["running"])
        ui.button(QRectF(bx - 50, by, 100, 32), "Pause" if tm.stopwatch["running"] else "Démarrer", tm.sw_toggle,
                  G["pause"] if tm.stopwatch["running"] else G["play"], accent=True)
        ui.button(QRectF(bx + 60, by, 100, 32), "Réinitialiser", tm.sw_reset, G["refresh"])
        laps = tm.stopwatch["laps"]
        lr = QRectF(body.left() - 8, by + 44, body.width() + 16, body.bottom() - by - 44)
        if not laps:
            ui.text(QRectF(lr.left(), lr.top() + 20, lr.width(), 18), "Les tours apparaîtront ici", font(8.5), T.text3, CENTER)
            return
        splits = [laps[i] - (laps[i + 1] if i + 1 < len(laps) else 0) for i in range(len(laps))]
        best, worst = min(splits), max(splits)

        def draw(y0):
            y = y0
            for i, (tot, sp) in enumerate(zip(laps, splits)):
                r = QRectF(lr.left() + 8, y, lr.width() - 22, 28)
                if i % 2 == 0:
                    ui.rect(r, T.layer, 4)
                col = T.success if sp == best and len(laps) > 1 else (T.critical if sp == worst and len(laps) > 1 else T.text)
                ui.text(QRectF(r.left() + 12, r.top(), 100, 28), f"Tour {len(laps) - i}", font(8.5), T.text2)
                ui.text(QRectF(r.center().x() - 60, r.top(), 120, 28), "+" + fmt_dur(sp) + f".{int(sp % 1 * 100):02d}",
                        font(9, W.DemiBold), col, CENTER)
                ui.text(QRectF(r.right() - 132, r.top(), 120, 28), fmt_dur(tot) + f".{int(tot % 1 * 100):02d}",
                        font(9), T.text2, RIGHT)
                y += 30
            return y - y0
        ui.scroll("laps", lr, draw)

    # ------------------------------------------------------------------ alarmes
    def _add_alarm(self, text):
        m = re.match(r"\s*(\d{1,2})\s*[:h]\s*(\d{2})?\s*(.*)$", text, re.I)
        if not m or int(m.group(1)) > 23:
            return False
        hhmm = f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
        rest = m.group(3).strip()
        days = []
        low = rest.lower()
        for pat, d in ((r"\b(semaine|lun-ven|jours ouvrés|en semaine)\b", [0, 1, 2, 3, 4]),
                       (r"\b(week-?end)\b", [5, 6]), (r"\b(tous les jours|quotidien|chaque jour)\b", list(range(7)))):
            mm = re.search(pat, low)
            if mm:
                days = d
                rest = (rest[:mm.start()] + rest[mm.end():]).strip()
        self.isl.timers.add_alarm(hhmm, rest or "Alarme", days)
        return True

    def _alarms(self, ui, body):
        tm = self.isl.timers
        ui.field(QRectF(body.left(), body.top(), body.width(), 30), "alarm_add",
                 "« 7h30 Réveil semaine », « 14:00 Sport week-end », « 22h Dormir tous les jours »",
                 on_submit=self._add_alarm, glyph=G["alarm"])
        nxt = tm.next_alarm()
        if nxt:
            delta = (nxt[0] - dt.datetime.now()).total_seconds()
            ui.text(QRectF(body.left(), body.top() + 36, body.width(), 18),
                    f"Prochaine alarme dans {fmt_minutes(delta // 60)} — {nxt[1]['label']}", font(8), T.text2)
        lr = QRectF(body.left() - 8, body.top() + 58, body.width() + 16, body.height() - 58)
        al = sorted(tm.alarms.items, key=lambda a: a["time"])
        if not al:
            ui.empty(lr, G["alarm"], "Aucune alarme")
            return

        def draw(y0):
            y = y0
            for a in al:
                r = QRectF(lr.left() + 8, y, lr.width() - 22, 52)
                if ui.visible(r):
                    on = a.get("enabled", True)
                    ui.card(r)
                    ui.text(QRectF(r.left() + 14, r.top() + 2, 100, 32), a["time"], font(17, W.DemiBold, True),
                            T.text if on else T.disabled)
                    days = a.get("days") or []
                    dtxt = "Une fois" if not days else ("Tous les jours" if len(days) == 7 else
                                                        ("En semaine" if days == [0, 1, 2, 3, 4] else
                                                         ("Week-end" if days == [5, 6] else " ".join(DAYS[d] for d in days))))
                    ui.text(QRectF(r.left() + 14, r.top() + 31, 200, 16), f"{a['label']} · {dtxt}", font(8), T.text2)
                    ui.toggle(QPointF(r.right() - 76, r.center().y()), on, lambda a=a: tm.toggle_alarm(a))
                    ui.icon_button(QPointF(r.right() - 22, r.center().y()), G["delete"],
                                   lambda a=a: tm.alarms.remove(a), 12, T.critical)
                y += 58
            return y - y0
        ui.scroll("alarms", lr, draw)

    # ------------------------------------------------------------------ statistiques
    def _stats(self, ui, body):
        tm = self.isl.timers
        st = tm.stats()
        cards = [("Aujourd'hui", fmt_minutes(st["today"]), G["focus"]),
                 ("Sessions", str(st["count_today"]), G["history"]),
                 ("7 jours", fmt_minutes(st["week"]), G["chart"]),
                 ("Série", f"{st['streak']} j", G["flag"])]
        cw = (body.width() - 18) / 4
        for i, (lbl, val, g) in enumerate(cards):
            r = QRectF(body.left() + i * (cw + 6), body.top(), cw, 56)
            ui.card(r)
            ui.glyph(QPointF(r.left() + 16, r.top() + 16), g, 11, T.accent)
            ui.text(QRectF(r.left() + 28, r.top() + 6, cw - 30, 20), lbl, font(7.5), T.text2)
            ui.text(QRectF(r.left() + 10, r.top() + 26, cw - 14, 26), val, font(12, W.DemiBold, True))
        # graphique 7 jours
        gr = QRectF(body.left(), body.top() + 66, body.width(), 110)
        ui.card(gr)
        mx = max(30.0, max(st["per_day"].values()))
        bw = (gr.width() - 40) / 7
        for i, d in enumerate(st["days"]):
            v = st["per_day"][d]
            h = (gr.height() - 44) * v / mx
            bx = gr.left() + 20 + i * bw + bw * 0.25
            col = T.accent if d == dt.date.today() else T.tint(T.accent, 140)
            if v > 0:
                ui.rect(QRectF(bx, gr.bottom() - 24 - h, bw * 0.5, h), col, 3)
            ui.text(QRectF(bx - 10, gr.bottom() - 22, bw * 0.5 + 20, 16), nlp.JOURS[d.weekday()][:3].capitalize(),
                    font(7), T.text3, CENTER)
            if v > 0:
                ui.text(QRectF(bx - 14, gr.bottom() - 40 - h, bw * 0.5 + 28, 14), f"{v:.0f}′", font(7), T.text2, CENTER)
        # sessions récentes
        y = gr.bottom() + 10
        ui.text(QRectF(body.left(), y, 200, 18), "Historique des sessions", font(8.5, W.DemiBold))
        lr = QRectF(body.left() - 8, y + 22, body.width() + 16, body.bottom() - y - 22)
        ses = tm.recent_sessions(30)
        if not ses:
            ui.text(QRectF(lr.left() + 8, lr.top(), lr.width(), 18),
                    "Terminez un Pomodoro ou un minuteur pour remplir l'historique", font(8), T.text3)
            return

        def draw(y0):
            yy = y0
            for s in ses:
                a = dt.datetime.fromtimestamp(s["start"])
                ui.glyph(QPointF(lr.left() + 18, yy + 11), G["focus"] if s["kind"] == "pomodoro" else G["timer"], 10, T.accent)
                ui.text(QRectF(lr.left() + 32, yy, 220, 22), s.get("label") or s["kind"], font(8.5))
                ui.text(QRectF(lr.right() - 200, yy, 186, 22),
                        f"{a.day}/{a.month} {a:%H:%M} · {fmt_minutes(s['duration'] // 60)}", font(8), T.text2, RIGHT)
                yy += 24
            return yy - y0
        ui.scroll("sessions", lr, draw)
