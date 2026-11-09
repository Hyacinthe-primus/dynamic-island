"""Onglet Agenda : à venir, semaine, mois, comptes (iCal Google / Outlook), ajout rapide."""
import datetime as dt
import time

from PySide6.QtCore import QPointF, QRectF

import icons
import nlp
from store import settings
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, until

CONTENT_H = 372
VIEWS = [("up", "À venir"), ("week", "Semaine"), ("month", "Mois"), ("accounts", "Comptes")]


class AgendaTab:
    key, label, glyph = "agenda", "Agenda", G["calendar"]

    def __init__(self, isl):
        self.isl = isl
        self.view = "up"
        self.week0 = self._monday(dt.date.today())
        self.month = dt.date.today().replace(day=1)
        self.sel_day = dt.date.today()
        self.editing = None

    @staticmethod
    def _monday(d):
        return d - dt.timedelta(days=d.weekday())

    def height(self):
        return CONTENT_H

    def set_view(self, v):
        self.view = v

    # ------------------------------------------------------------------
    def paint(self, ui, cr):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        ui.segmented(QRectF(x0 - 6, cr.top(), 0, 30), VIEWS, self.view, self.set_view)
        y = cr.top() + 36
        if self.view != "accounts":
            ph = "Modifier : texte + date (Entrée)" if self.editing else \
                "Ajouter : « Réunion demain 14h30 », « Anniversaire Léa 12/03 »"
            ui.field(QRectF(x0, y, x1 - x0, 30), "agenda_add", ph, on_submit=self._submit, glyph=G["add"])
            y += 38
        body = QRectF(cr.left() + 8, y, cr.width() - 16, cr.bottom() - y - 8)
        getattr(self, "_" + self.view)(ui, body)

    def _submit(self, text):
        if self.editing:
            occ, self.editing = self.editing, None
            r = nlp.parse(text)
            date = r["date"] or dt.date.fromtimestamp(occ["start"])
            if r["time"]:
                s = time.mktime(dt.datetime.combine(date, r["time"]).timetuple())
                self.isl.agenda.update(occ, title=r["title"] or occ["title"], start=s,
                                       end=s + (occ["end"] - occ["start"] if not occ["all_day"] else 3600),
                                       all_day=False)
            else:
                s = time.mktime(dt.datetime(date.year, date.month, date.day).timetuple())
                self.isl.agenda.update(occ, title=r["title"] or occ["title"], start=s, end=s + 86400, all_day=True)
            return True
        ev = self.isl.agenda.quick_add(text)
        if ev:
            self.isl.show_alert("event", "Événement ajouté", ev["title"], T.accent, G["calendar"])
            self.sel_day = dt.date.fromtimestamp(ev["start"])
        return ev is not None

    def edit(self, occ):
        self.editing = occ
        d = dt.datetime.fromtimestamp(occ["start"])
        txt = f"{occ['title']} {d.day:02d}/{d.month:02d}"
        if not occ["all_day"]:
            txt += f" {d.hour}h{d.minute:02d}"
        self.isl.fields["agenda_add"] = txt
        self.isl.focus("agenda_add")

    # ------------------------------------------------------------------ à venir
    def _up(self, ui, body):
        isl = self.isl
        evs = isl.agenda.upcoming(40, 60)
        if not evs:
            ui.empty(body, G["calendar"], "Aucun événement à venir",
                     "Ajoutez-en ci-dessus ou connectez Google / Outlook dans « Comptes »")
            return

        def draw(y0):
            y = y0
            last = None
            for o in evs:
                d = dt.date.fromtimestamp(max(o["start"], time.time()) if o["all_day"] else o["start"])
                if d != last:
                    last = d
                    ui.text(QRectF(body.left() + 8, y + 4, 300, 18), self._day_label(d), font(8, W.DemiBold), T.text2)
                    y += 24
                y = self.event_row(ui, body.left() + 4, body.right() - 8, y, o)
            return y - y0
        ui.scroll("agenda_up", body, draw)

    @staticmethod
    def _day_label(d):
        today = dt.date.today()
        base = f"{nlp.JOURS[d.weekday()]} {d.day} {nlp.MOIS[d.month - 1]}"
        if d == today:
            return "Aujourd'hui · " + base
        if d == today + dt.timedelta(days=1):
            return "Demain · " + base
        return base.capitalize()

    def event_row(self, ui, x0, x1, y, o, compact=False):
        isl = self.isl
        now = time.time()
        r = QRectF(x0, y, x1 - x0, 46)
        if ui.visible(r):
            hov = ui.row_hover(r)
            ui.rect(r, T.layer2 if hov else T.layer, 6, T.stroke)
            col = T.orange if o.get("birthday") else (T.accent if o.get("local") else T.purple)
            ui.rect(QRectF(r.left() + 6, r.top() + 8, 3, 30), col, 1.5)
            if o["all_day"]:
                when = "Toute la journée"
            else:
                a, b = dt.datetime.fromtimestamp(o["start"]), dt.datetime.fromtimestamp(o["end"])
                when = f"{a:%H:%M} – {b:%H:%M}"
            right = 10
            if o.get("meet_url") and o["end"] > now:
                br = QRectF(r.right() - 100, r.top() + 9, 90, 28)
                ui.button(br, "Rejoindre", lambda u=o["meet_url"]: isl.open_url(u), G["video"], accent=True)
                right = 106
            elif not o["all_day"] and o["start"] > now and o["start"] - now < 86400:
                ui.text(QRectF(r.right() - 100, r.top(), 90, 46), until(o["start"] - now), font(8, W.DemiBold),
                        T.accent, RIGHT)
                right = 100
            elif not o["all_day"] and o["start"] <= now < o["end"]:
                right = 90
                ui.badge(r.right() - 80, r.top() + 15, "En cours", T.success)
            if o.get("local") and hov:
                ui.icon_button(QPointF(r.right() - right - 14, r.center().y()), G["delete"],
                               lambda o=o: isl.agenda.delete(o), 12, T.critical, 26)
                ui.icon_button(QPointF(r.right() - right - 42, r.center().y()), G["edit"],
                               lambda o=o: self.edit(o), 12, None, 26)
                right += 60
            title = o["title"]
            tx = r.left() + 18
            if o.get("birthday"):
                title += f" ({o['age']} ans)" if o.get("age") else ""
                icons.cake(ui.p, QRectF(tx, r.top() + 6, 16, 16))
                tx += 20
            ui.text(QRectF(tx, r.top() + 6, r.right() - 8 - right - tx, 18), title, font(9, W.DemiBold))
            src = o.get("meet_app") or o.get("location") or o.get("source", "")
            ui.text(QRectF(r.left() + 18, r.top() + 24, r.width() - 26 - right, 16),
                    when + (" · " + src if src else ""), font(8), T.text2)
        return y + 52

    # ------------------------------------------------------------------ semaine
    def _week(self, ui, body):
        isl = self.isl
        days = [self.week0 + dt.timedelta(days=i) for i in range(7)]
        y = body.top()
        ui.icon_button(QPointF(body.left() + 14, y + 12), G["left"], lambda: self._shift_week(-1), 11)
        ui.icon_button(QPointF(body.left() + 42, y + 12), G["right"], lambda: self._shift_week(1), 11)
        title = f"{days[0].day} {nlp.MOIS[days[0].month - 1][:4]}. – {days[6].day} {nlp.MOIS[days[6].month - 1][:4]}. {days[6].year}"
        ui.text(QRectF(body.left() + 60, y, 260, 24), title, font(9, W.DemiBold))
        ui.button(QRectF(body.right() - 92, y, 84, 24), "Cette semaine",
                  lambda: setattr(self, "week0", self._monday(dt.date.today())))
        y += 30
        counts = isl.agenda.count_by_day(days[0], days[6])
        cw = (body.width() - 8) / 7
        today = dt.date.today()
        for i, d in enumerate(days):
            cx = body.left() + 4 + i * cw
            col = QRectF(cx + 1, y, cw - 2, body.bottom() - y)
            ui.rect(col, T.layer2 if d == today else T.layer, 6, T.stroke)
            ui.text(QRectF(cx, y + 4, cw, 14), nlp.JOURS[i][:3].capitalize(), font(7.5, W.DemiBold),
                    T.accent if d == today else T.text3, CENTER)
            ui.text(QRectF(cx, y + 18, cw, 20), str(d.day), font(11, W.DemiBold, True),
                    T.accent if d == today else T.text, CENTER)
            ui.hit(QRectF(cx, y, cw, 40), lambda d=d: self._open_day(d))
            yy = y + 44
            for o in counts.get(d, [])[:6]:
                er = QRectF(cx + 4, yy, cw - 8, 32)
                c = T.orange if o.get("birthday") else (T.accent if o.get("local") else T.purple)
                ui.rect(er, T.tint(c, 45), 4)
                ui.rect(QRectF(er.left(), er.top(), 2, er.height()), c, 1)
                t = "Journée" if o["all_day"] else dt.datetime.fromtimestamp(o["start"]).strftime("%H:%M")
                ui.text(QRectF(er.left() + 6, er.top() + 2, er.width() - 8, 14), t, font(6.5, W.DemiBold), T.text2)
                ui.text(QRectF(er.left() + 6, er.top() + 15, er.width() - 8, 15), o["title"], font(7.5), T.text)
                if o.get("meet_url"):
                    ui.hit(er, lambda u=o["meet_url"]: isl.open_url(u))
                yy += 36
            extra = len(counts.get(d, [])) - 6
            if extra > 0:
                ui.text(QRectF(cx, yy, cw, 14), f"+{extra}", font(7.5), T.text3, CENTER)

    def _shift_week(self, n):
        self.week0 += dt.timedelta(days=7 * n)

    def _open_day(self, d):
        self.sel_day = d
        self.month = d.replace(day=1)
        self.view = "month"

    # ------------------------------------------------------------------ mois
    def _month(self, ui, body):
        isl = self.isl
        m0 = self.month
        y = body.top()
        gw = 7 * 38
        ui.icon_button(QPointF(body.left() + 14, y + 12), G["left"], lambda: self._shift_month(-1), 11)
        ui.icon_button(QPointF(body.left() + gw - 10, y + 12), G["right"], lambda: self._shift_month(1), 11)
        ui.text(QRectF(body.left() + 30, y, gw - 60, 24), f"{nlp.MOIS[m0.month - 1].capitalize()} {m0.year}",
                font(9.5, W.DemiBold), T.text, CENTER)
        y += 28
        self.month_grid(ui, QRectF(body.left() + 4, y, gw, body.bottom() - y), m0, self.sel_day,
                        lambda d: setattr(self, "sel_day", d))
        # liste du jour choisi
        lx = body.left() + gw + 18
        lr = QRectF(lx, body.top(), body.right() - lx, body.height())
        ui.text(QRectF(lx, lr.top(), lr.width(), 24), self._day_label(self.sel_day), font(9, W.DemiBold))
        evs = isl.agenda.day(self.sel_day)
        if not evs:
            ui.text(QRectF(lx, lr.top() + 30, lr.width(), 18), "Aucun événement", font(8.5), T.text3)
            return

        def draw(y0):
            yy = y0
            for o in evs:
                yy = self.event_row(ui, lx, lr.right() - 6, yy, o)
            return yy - y0
        ui.scroll("agenda_day", QRectF(lx - 2, lr.top() + 28, lr.width() + 2, lr.height() - 28), draw)

    def _shift_month(self, n):
        m = self.month.month - 1 + n
        self.month = dt.date(self.month.year + m // 12, m % 12 + 1, 1)

    def month_grid(self, ui, r, m0, sel, on_click, mini=False):
        cw = r.width() / 7
        for i in range(7):
            ui.text(QRectF(r.left() + i * cw, r.top(), cw, 16), nlp.JOURS[i][:2].capitalize(), font(7, W.DemiBold),
                    T.text3, CENTER)
        first = m0 - dt.timedelta(days=m0.weekday())
        last = first + dt.timedelta(days=41)
        counts = self.isl.agenda.count_by_day(first, last) if not mini else self.isl.agenda.count_by_day(first, last)
        rh = min(38.0, (r.height() - 18) / 6)
        today = dt.date.today()
        for k in range(42):
            d = first + dt.timedelta(days=k)
            cx = r.left() + (k % 7) * cw
            cy = r.top() + 18 + (k // 7) * rh
            cell = QRectF(cx + 1, cy + 1, cw - 2, rh - 2)
            c = cell.center()
            rad = min(cw, rh) / 2 - 3
            if d == today:
                ui.p.setPen(T.accent)
                ui.p.setBrush(T.accent)
                ui.p.drawEllipse(c, rad, rad)
            elif d == sel:
                ui.rect(cell.adjusted(2, 2, -2, -2), T.layer2, 4, T.stroke2)
            elif ui.hovering(cell):
                ui.rect(cell.adjusted(2, 2, -2, -2), T.hover, 4)
            colr = T.on_accent if d == today else (T.text if d.month == m0.month else T.disabled)
            ui.text(QRectF(cell.left(), cell.top() - (3 if counts.get(d) else 0), cell.width(), cell.height()),
                    str(d.day), font(7.5 if mini else 8.5, W.DemiBold if d == today else W.Normal), colr, CENTER)
            evs = counts.get(d)
            if evs:
                n = min(3, len(evs))
                for j in range(n):
                    o = evs[j]
                    dc = T.on_accent if d == today else (T.orange if o.get("birthday") else T.accent)
                    ui.p.setPen(dc)
                    ui.p.setBrush(dc)
                    ui.p.drawEllipse(QPointF(c.x() + (j - (n - 1) / 2) * 5, c.y() + rad - 4), 1.6, 1.6)
            ui.hit(cell, lambda d=d: on_click(d))

    # ------------------------------------------------------------------ comptes
    def _accounts(self, ui, body):
        isl = self.isl
        x0, x1 = body.left() + 8, body.right() - 8
        y = body.top() + 2
        ui.text(QRectF(x0, y, x1 - x0, 18), "Synchroniser Google Agenda, Outlook ou Teams", font(9.5, W.DemiBold))
        y += 22
        ui.wrap(QRectF(x0, y, x1 - x0, 46),
                "Google : Paramètres de l'agenda › « Adresse secrète au format iCal ». Outlook : Paramètres › "
                "Calendrier › Calendriers partagés › Publier › lien ICS. Les liens Teams / Zoom / Meet des "
                "événements sont détectés automatiquement.", font(8), T.text2, lines=3)
        y += 52
        ui.field(QRectF(x0, y, x1 - x0, 30), "ics_url", "Coller l'adresse iCal (https://… ou webcal://…) puis Entrée",
                 on_submit=lambda t: isl.agenda.add_feed(t), glyph=G["link"])
        y += 40
        feeds = isl.agenda.feeds
        if not feeds:
            ui.text(QRectF(x0, y, x1 - x0, 20), "Aucun calendrier connecté pour l'instant.", font(8.5), T.text3)
            y += 26
        for f in feeds:
            r = QRectF(x0, y, x1 - x0, 40)
            ui.card(r)
            ok, msg, n = isl.agenda.remote_status.get(f["url"], (None, "Synchronisation…", 0))
            ui.glyph(QPointF(r.left() + 18, r.center().y()), G["cloud"], 14,
                     T.success if ok else (T.critical if ok is False else T.text3))
            ui.text(QRectF(r.left() + 36, r.top() + 4, r.width() - 120, 18), f["name"], font(9, W.DemiBold))
            ui.text(QRectF(r.left() + 36, r.top() + 21, r.width() - 120, 15), msg, font(7.5),
                    T.critical if ok is False else T.text2)
            ui.button(QRectF(r.right() - 76, r.top() + 8, 68, 24), "Retirer",
                      lambda u=f["url"]: isl.agenda.remove_feed(u), danger=True)
            y += 46
        y += 4
        ui.text(QRectF(x0, y, 200, 24), "Rappel avant les réunions", font(8.5, W.Medium))
        x = x0 + 190
        cur = settings.get("remind_min", 10)
        for m in (0, 5, 10, 15, 30):
            w = ui.chip_w(f"{m} min")
            ui.chip(QRectF(x, y + 1, w, 22), f"{m} min", m == cur, lambda m=m: settings.set("remind_min", m))
            x += w + 4
        y += 30
        ui.button(QRectF(x0, y, 140, 26), "Actualiser maintenant", isl.agenda.refresh, G["refresh"])
