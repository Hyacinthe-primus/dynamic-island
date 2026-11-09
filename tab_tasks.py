"""Onglet Tâches : aujourd'hui, toutes, projets, notes rapides."""
from PySide6.QtCore import QPointF, QRectF

from tasks import PRIO_LABEL
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago

CONTENT_H = 372
VIEWS = [("today", "Aujourd'hui"), ("all", "Toutes"), ("projects", "Projets"), ("notes", "Notes")]


class TasksTab:
    key, label, glyph = "tasks", "Tâches", G["tasks"]

    def __init__(self, isl):
        self.isl = isl
        self.view = "today"
        self.project = None
        self.show_done = False
        self.editing_note = None

    def height(self):
        return CONTENT_H

    def set_view(self, v):
        self.view = v

    def paint(self, ui, cr):
        x0, x1 = cr.left() + 16, cr.right() - 16
        ui.segmented(QRectF(x0 - 6, cr.top(), 0, 30), VIEWS, self.view, self.set_view)
        body = QRectF(x0, cr.top() + 38, x1 - x0, cr.height() - 46)
        if self.view == "notes":
            self._notes(ui, body)
        else:
            self._tasks(ui, body)

    # ------------------------------------------------------------------ tâches
    def _tasks(self, ui, body):
        isl = self.isl
        tk = isl.tasks
        ph = "Nouvelle tâche… « Envoyer devis demain 9h !haute #client »"
        if self.view == "projects" and self.project:
            ph = f"Nouvelle tâche dans #{self.project}…"
        ui.field(QRectF(body.left(), body.top(), body.width(), 30), "task_add", ph,
                 on_submit=self._add, glyph=G["add"])
        y = body.top() + 38
        if self.view == "projects":
            x = body.left()
            for pr in [None] + tk.projects():
                lbl = "Tous" if pr is None else "#" + pr
                w = ui.chip_w(lbl)
                if x + w > body.right():
                    break
                ui.chip(QRectF(x, y, w, 22), lbl, pr == self.project, lambda pr=pr: setattr(self, "project", pr))
                x += w + 4
            y += 30
        if self.view != "today":
            ui.text(QRectF(body.right() - 180, body.top() - 36, 130, 28), "Afficher terminées", font(8), T.text2, RIGHT)
            ui.toggle(QPointF(body.right() - 22, body.top() - 22), self.show_done,
                      lambda: setattr(self, "show_done", not self.show_done))
        items = tk.query(self.view if self.view == "today" else "all",
                         self.project if self.view == "projects" else None, self.show_done)
        lr = QRectF(body.left() - 8, y, body.width() + 16, body.bottom() - y)
        if not items:
            msg = "Tout est fait pour aujourd'hui" if self.view == "today" else "Aucune tâche"
            ui.empty(lr, G["tasks"], msg, "Astuce : !haute / !moyenne / !faible, #projet, demain 9h, lundi…")
            return

        def draw(y0):
            yy = y0
            for t in items:
                yy = self.task_row(ui, lr.left() + 4, lr.right() - 12, yy, t)
            return yy - y0
        ui.scroll("tasks_" + self.view, lr, draw)

    def _add(self, text):
        if self.view == "projects" and self.project and "#" not in text:
            text += f" #{self.project}"
        t = self.isl.tasks.quick_add(text)
        return t is not None

    def task_row(self, ui, x0, x1, y, t):
        tk = self.isl.tasks
        r = QRectF(x0, y, x1 - x0, 40)
        if ui.visible(r):
            hov = ui.row_hover(r)
            ui.rect(r, T.layer2 if hov else T.layer, 6, T.stroke)
            pr = t.get("priority", 0)
            col = {3: T.critical, 2: T.orange, 1: T.accent}.get(pr, T.track)
            ui.checkbox(QPointF(r.left() + 18, r.center().y()), t.get("done"), lambda t=t: tk.toggle(t), col,
                        round_=True, size=18)
            done = t.get("done")
            tx = r.left() + 36
            right = 12 + (70 if hov else 0)
            f = font(9, W.Medium)
            ui.text(QRectF(tx, r.top() + 3, r.width() - 36 - right, 18), t["title"], f, T.text3 if done else T.text)
            if done:
                w = min(ui.tw(t["title"], f), r.width() - 36 - right)
                ui.p.setPen(T.text3)
                ui.p.drawLine(QPointF(tx, r.top() + 12), QPointF(tx + w, r.top() + 12))
            x = tx
            lbl, late = tk.due_label(t)
            meta_y = r.top() + 22
            if lbl:
                ui.glyph(QPointF(x + 5, meta_y + 8), G["calendar"], 9, T.critical if late else T.text3)
                ui.text(QRectF(x + 13, meta_y, 110, 16), lbl, font(7.5), T.critical if late else T.text2)
                x += 18 + ui.tw(lbl, font(7.5)) + 8
            if t.get("remind") and not t.get("reminded"):
                ui.glyph(QPointF(x + 5, meta_y + 8), G["bell"], 9, T.text3)
                x += 16
            if pr:
                x += ui.badge(x, meta_y, PRIO_LABEL[pr], col) + 5
            if t.get("project"):
                x += ui.badge(x, meta_y, "#" + t["project"], T.text2) + 5
            if hov:
                ui.icon_button(QPointF(r.right() - 20, r.center().y()), G["delete"], lambda t=t: tk.delete(t), 12,
                               T.critical, 26)
                ui.icon_button(QPointF(r.right() - 48, r.center().y()), G["flag"], lambda t=t: tk.cycle_priority(t),
                               12, col if pr else None, 26)
        return y + 44

    # ------------------------------------------------------------------ notes
    def _notes(self, ui, body):
        isl = self.isl
        tk = isl.tasks
        half = (body.width() - 8) / 2
        ph = "Modifier la note (Entrée = enregistrer, vide = supprimer)" if self.editing_note else \
            "Nouvelle note rapide… (Entrée)"
        ui.field(QRectF(body.left(), body.top(), half + 70, 30), "note_add", ph, on_submit=self._save_note, glyph=G["note"])
        ui.field(QRectF(body.left() + half + 78, body.top(), half - 70, 30), "note_search", "Rechercher", glyph=G["search"])
        notes = tk.query_notes(isl.fields.get("note_search", ""))
        lr = QRectF(body.left() - 8, body.top() + 38, body.width() + 16, body.height() - 38)
        if not notes:
            ui.empty(lr, G["note"], "Aucune note", "Les notes épinglées restent en haut")
            return

        def draw(y0):
            cw = (lr.width() - 30) / 2
            heights = [y0, y0]
            for n in notes:
                col = 0 if heights[0] <= heights[1] else 1
                x = lr.left() + 8 + col * (cw + 6)
                y = heights[col]
                lines = min(6, max(1, len(n["text"]) // 34 + n["text"].count("\n") + 1))
                h = 34 + lines * 16
                r = QRectF(x, y, cw, h)
                if ui.visible(r):
                    hov = ui.row_hover(r)
                    sel = self.editing_note is n
                    ui.rect(r, T.tint(T.caution, 28) if n.get("pinned") else (T.layer2 if hov else T.layer), 6,
                            T.accent if sel else T.stroke)
                    ui.wrap(QRectF(r.left() + 10, r.top() + 8, cw - 20, lines * 16), n["text"].replace("\n", " "),
                            font(8.5), T.text, lines)
                    ui.text(QRectF(r.left() + 10, r.bottom() - 20, cw - 80, 16), ago(n.get("mtime", 0)), font(7), T.text3)
                    if n.get("pinned"):
                        ui.glyph(QPointF(r.right() - 14, r.bottom() - 12), G["pinned"], 10, T.orange)
                    ui.row_hit(r, lambda n=n: self._edit_note(n))
                    if hov:
                        bx = r.right() - 14
                        ui.icon_button(QPointF(bx, r.bottom() - 12), G["delete"], lambda n=n: tk.delete_note(n), 10,
                                       T.critical, 22)
                        ui.icon_button(QPointF(bx - 24, r.bottom() - 12), G["pinned"] if n.get("pinned") else G["pin"],
                                       lambda n=n: tk.toggle_pin_note(n), 10, T.orange if n.get("pinned") else None, 22)
                        ui.icon_button(QPointF(bx - 48, r.bottom() - 12), G["copy"],
                                       lambda n=n: self.isl.copy_text(n["text"]), 10, None, 22)
                heights[col] = y + h + 6
            return max(heights) - y0
        ui.scroll("notes", lr, draw)

    def _edit_note(self, n):
        self.editing_note = n
        self.isl.fields["note_add"] = n["text"]
        self.isl.focus("note_add")

    def _save_note(self, text):
        if self.editing_note is not None:
            self.isl.tasks.edit_note(self.editing_note, text)
            self.editing_note = None
            return True
        return self.isl.tasks.add_note(text) is not None
