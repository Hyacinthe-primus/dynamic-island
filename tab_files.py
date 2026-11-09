"""Onglet Fichiers : étagère (glisser-déposer), téléchargements, récents, dossiers favoris."""
import os
import time

from PySide6.QtCore import QPointF, QRectF

from files import DOWNLOADS, human
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago, fmt_dur

CONTENT_H = 372
VIEWS = [("shelf", "Étagère"), ("downloads", "Téléchargements"), ("recent", "Récents"), ("favorites", "Favoris")]


class FilesTab:
    key, label, glyph = "files", "Fichiers", G["folder"]

    def __init__(self, isl):
        self.isl = isl
        self.view = "shelf"
        self.pick = None   # "copy" | "move" : choix de la destination

    def height(self):
        return CONTENT_H

    def set_view(self, v):
        self.view = v
        self.pick = None

    def paint(self, ui, cr):
        x0 = cr.left() + 16
        ui.segmented(QRectF(x0 - 6, cr.top(), 0, 30), VIEWS, self.view, self.set_view)
        n = len(self.isl.files.downloads)
        if n:
            fa = font(8.5, W.DemiBold)
            bx = x0 - 6 + ui.tw(VIEWS[0][1], fa) + 22 + 2 + ui.tw(VIEWS[1][1], fa) + 16
            ui.badge(bx, cr.top() + 2, str(n), T.accent)
        body = QRectF(cr.left() + 16, cr.top() + 38, cr.width() - 32, cr.height() - 46)
        getattr(self, "_" + self.view)(ui, body)

    # ------------------------------------------------------------------ outils
    def file_row(self, ui, x0, x1, y, path, sub, actions, h=40):
        r = QRectF(x0, y, x1 - x0, h)
        if not ui.visible(r):
            return y + h + 2
        hov = ui.row_hover(r)
        if hov:
            ui.rect(r, T.hover, 6)
        ui.file_icon(QRectF(r.left() + 8, r.top() + (h - 26) / 2, 26, 26), path)
        right = 10 + (len(actions) * 30 if hov else 0)
        ui.text(QRectF(r.left() + 44, r.top() + 3, r.width() - 50 - right, 18),
                os.path.basename(path.rstrip("\\")) or path, font(9, W.Medium))
        ui.text(QRectF(r.left() + 44, r.top() + 20, r.width() - 50 - right, 16), sub, font(7.5), T.text3)
        ui.drag_row(QRectF(r.left(), r.top(), r.width() - right, h), [path], lambda p=path: self.isl.files.open(p))
        if hov:
            bx = r.right() - 18
            for g, fn, col in actions:
                ui.icon_button(QPointF(bx, r.center().y()), g, fn, 12, col, 26)
                bx -= 30
        return y + h + 2

    def _destinations(self, ui, body, paths):
        fl = self.isl.files
        ui.text(QRectF(body.left(), body.top(), body.width(), 20),
                ("Déplacer" if self.pick == "move" else "Copier") + f" {len(paths)} élément(s) vers…", font(9, W.DemiBold))
        ui.button(QRectF(body.right() - 80, body.top() - 2, 80, 26), "Annuler", lambda: setattr(self, "pick", None))
        y = body.top() + 30
        for d in fl.favorites:
            y = self.file_row(ui, body.left() - 4, body.right() + 4, y, d, d, [])
            ui.hit(QRectF(body.left(), y - 42, body.width(), 40), lambda d=d: self._do(paths, d))
        ui.button(QRectF(body.left(), y + 6, 160, 28), "Autre dossier…", lambda: self._other(paths), G["folder"])

    def _do(self, paths, dest):
        self.isl.files.transfer(paths, dest, move=self.pick == "move")
        self.pick = None

    def _other(self, paths):
        from PySide6.QtWidgets import QFileDialog
        mode = self.pick
        self.isl.close_island(restore_focus=False)
        d = QFileDialog.getExistingDirectory(None, "Choisir la destination", os.path.expanduser("~"))
        if d:
            self.isl.files.transfer(paths, d, move=mode == "move")
        self.pick = None

    # ------------------------------------------------------------------ étagère
    def _shelf(self, ui, body):
        fl = self.isl.files
        shelf = fl.shelf
        if self.pick:
            return self._destinations(ui, body, shelf)
        drop = self.isl.drop_hover
        if not shelf or drop:
            r = body.adjusted(0, 4, 0, -4)
            ui.rect(r, T.tint(T.accent, 30) if drop else T.layer, 8, T.accent if drop else T.stroke2)
            ui.empty(r, G["download"] if "download" in G else "",
                     "Déposez ici" if drop else "Glissez des fichiers dans l'île",
                     "Ils restent en attente ici : ouvrez-les, copiez-les, ou faites-les glisser vers une autre application")
            return
        x = body.left()
        for label, g, fn in (("Copier vers…", G["copy"], lambda: setattr(self, "pick", "copy")),
                             ("Déplacer vers…", "", lambda: setattr(self, "pick", "move")),
                             ("Presse-papiers", G["clip"], lambda: self.isl.copy_files(shelf)),
                             ("Vider", G["delete"], fl.clear_shelf)):
            w = ui.tw(label, font(8.5, W.Medium)) + 40
            ui.button(QRectF(x, body.top(), w, 28), label, fn, g, danger=label == "Vider")
            x += w + 6
        ui.text(QRectF(body.right() - 160, body.top(), 160, 28), f"{len(shelf)} élément(s)", font(8), T.text3, RIGHT)
        lr = QRectF(body.left() - 8, body.top() + 36, body.width() + 16, body.height() - 36)

        def draw(y0):
            y = y0
            for p in shelf:
                size = human(os.path.getsize(p)) if os.path.isfile(p) else "Dossier"
                y = self.file_row(ui, lr.left() + 4, lr.right() - 12, y, p, f"{size} · {os.path.dirname(p)}",
                                  [(G["close"], lambda p=p: fl.remove_from_shelf(p), None),
                                   (G["folder"], lambda p=p: fl.reveal(p), None),
                                   (G["open"], lambda p=p: fl.open(p), None)])
            ui.text(QRectF(lr.left() + 8, y + 4, lr.width() - 16, 16),
                    "Astuce : faites glisser une ligne vers l'Explorateur, un e-mail, WhatsApp Web…", font(7.5), T.text3)
            return y - y0 + 26
        ui.scroll("shelf", lr, draw)

    # ------------------------------------------------------------------ téléchargements
    def _downloads(self, ui, body):
        fl = self.isl.files

        def draw(y0):
            x0, x1 = body.left(), body.right() - 10
            y = y0
            ui.text(QRectF(x0, y, 300, 18), "En cours", font(8.5, W.DemiBold))
            y += 22
            if not fl.downloads:
                ui.text(QRectF(x0, y, 400, 18), "Aucun téléchargement en cours", font(8), T.text3)
                y += 24
            for d in fl.downloads:
                r = QRectF(x0, y, x1 - x0, 58)
                ui.card(r)
                ui.file_icon(QRectF(r.left() + 10, r.top() + 10, 24, 24), d["target"])
                ui.text(QRectF(r.left() + 44, r.top() + 6, r.width() - 160, 18), d["name"], font(9, W.Medium))
                if d["total"]:
                    frac = d["size"] / d["total"]
                    ui.text(QRectF(r.right() - 110, r.top() + 6, 100, 18), f"{frac * 100:.0f} %", font(10, W.DemiBold),
                            T.accent, RIGHT)
                    ui.bar(QRectF(r.left() + 44, r.top() + 28, r.width() - 56, 4), frac)
                    eta = f" · reste {fmt_dur(d['eta'])}" if d["eta"] else ""
                    sub = f"{human(d['size'])} / {human(d['total'])} · {human(d['speed'])}/s{eta}"
                else:
                    t = (time.time() * 1.5) % 1
                    ui.bar(QRectF(r.left() + 44, r.top() + 28, r.width() - 56, 4), 0)
                    ui.rect(QRectF(r.left() + 44 + (r.width() - 116) * t, r.top() + 28, 60, 4), T.accent, 2)
                    sub = (f"{human(d['size'])} · {human(d['speed'])}/s" if d["speed"] > 0 else
                           f"{human(d['size'])} · en pause") + " · taille totale inconnue"
                ui.text(QRectF(r.left() + 44, r.top() + 36, r.width() - 56, 16), f"{d['browser']} · {sub}", font(7.5), T.text2)
                y += 64
            y += 6
            ui.text(QRectF(x0, y, 300, 18), "Récemment téléchargés", font(8.5, W.DemiBold))
            ui.link(QRectF(x1 - 120, y, 120, 18), "Ouvrir le dossier ›", lambda: fl.open(DOWNLOADS))
            y += 22
            try:
                done = sorted((os.path.join(DOWNLOADS, f) for f in os.listdir(DOWNLOADS)
                               if not f.lower().endswith((".crdownload", ".part", ".tmp", ".partial"))),
                              key=os.path.getmtime, reverse=True)[:12]
            except OSError:
                done = []
            for p in done:
                y = self.file_row(ui, x0 - 4, x1, y, p, f"{human(os.path.getsize(p)) if os.path.isfile(p) else 'Dossier'}"
                                  f" · {ago(os.path.getmtime(p))}",
                                  [(G["add"], lambda p=p: fl.add_to_shelf([p]), None),
                                   (G["folder"], lambda p=p: fl.reveal(p), None)])
            return y - y0
        ui.scroll("downloads", QRectF(body.left() - 4, body.top(), body.width() + 8, body.height()), draw)

    # ------------------------------------------------------------------ récents
    def _recent(self, ui, body):
        fl = self.isl.files
        items = fl.recent
        if not items:
            ui.empty(body, G["history"], "Aucun fichier récent")
            return

        def draw(y0):
            y = y0
            for it in items:
                y = self.file_row(ui, body.left() - 4, body.right() - 10, y, it["path"],
                                  f"{ago(it['mtime'])} · {os.path.dirname(it['path'])}",
                                  [(G["add"], lambda p=it["path"]: fl.add_to_shelf([p]), None),
                                   (G["folder"], lambda p=it["path"]: fl.reveal(p), None)])
            return y - y0
        ui.scroll("recent_files", QRectF(body.left() - 4, body.top(), body.width() + 8, body.height()), draw)

    # ------------------------------------------------------------------ favoris
    def _favorites(self, ui, body):
        fl = self.isl.files
        favs = fl.favorites
        ui.button(QRectF(body.left(), body.top(), 170, 28), "Ajouter un dossier…", self._add_fav, G["add"])
        ui.text(QRectF(body.left() + 180, body.top(), body.width() - 180, 28),
                "Survolez un dossier pour créer un raccourci sur le Bureau", font(7.5), T.text3)
        cols = 4
        gap = 8
        cw = (body.width() - gap * (cols - 1)) / cols
        for i, d in enumerate(favs):
            r = QRectF(body.left() + (i % cols) * (cw + gap), body.top() + 38 + (i // cols) * 78, cw, 70)
            hov = ui.hovering(r)
            ui.rect(r, T.layer2 if hov else T.layer, 6, T.stroke)
            ui.file_icon(QRectF(r.center().x() - 14, r.top() + 10, 28, 28), d)
            ui.text(QRectF(r.left() + 6, r.top() + 44, r.width() - 12, 18), os.path.basename(d.rstrip("\\")) or d,
                    font(8, W.Medium), T.text, CENTER)
            ui.drag_row(r, [d], lambda d=d: fl.open(d))
            if hov:
                ui.icon_button(QPointF(r.right() - 13, r.top() + 13), G["close"], lambda d=d: fl.remove_favorite(d), 9, None, 20)
                ui.icon_button(QPointF(r.left() + 13, r.top() + 13), G["link"], lambda d=d: self._shortcut(d), 9, None, 20)

    def _add_fav(self):
        from PySide6.QtWidgets import QFileDialog
        self.isl.close_island(restore_focus=False)
        d = QFileDialog.getExistingDirectory(None, "Dossier favori", os.path.expanduser("~"))
        if d:
            self.isl.files.add_favorite(os.path.normpath(d))

    def _shortcut(self, d):
        lnk = self.isl.files.desktop_shortcut(d)
        self.isl.show_alert("files", "Raccourci créé sur le Bureau" if lnk else "Raccourci impossible",
                            os.path.basename(d), T.success if lnk else T.critical, G["link"])
