"""Onglet Presse-papiers : historique intelligent."""
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainterPath, QPixmap

from clipboard import CATEGORIES, KIND_LABEL
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago

CONTENT_H = 372
ROW = 50


class ClipTab:
    key, label, glyph = "clip", "Presse-papiers", G["clip"]

    def __init__(self, isl):
        self.isl = isl
        self.category = "all"
        self.sel = 0
        self.thumbs = {}
        self._cache = (None, [])
        self.version = 0
        isl.clip.changed.connect(self._changed)

    def _changed(self):
        self.version += 1

    def height(self):
        return CONTENT_H

    def items(self):
        key = (self.isl.fields.get("clip_search", ""), self.category, self.version)
        if self._cache[0] != key:
            self._cache = (key, self.isl.clip.query(key[0], self.category))
            self.sel = min(self.sel, max(0, len(self._cache[1]) - 1))
        return self._cache[1]

    def _reset(self, *_):
        self.sel = 0
        self.isl.scrolls.pop("clip", None)

    def set_cat(self, k):
        self.category = k
        self._reset()

    # ------------------------------------------------------------------ clavier
    def key_event(self, e):
        k = e.key()
        items = self.items()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if items:
                self.isl.paste_item(items[self.sel])
            return True
        if k == Qt.Key.Key_Down:
            self.sel = min(len(items) - 1, self.sel + 1)
            self._ensure()
            return True
        if k == Qt.Key.Key_Up:
            self.sel = max(0, self.sel - 1)
            self._ensure()
            return True
        if k == Qt.Key.Key_Delete and items:
            self.isl.clip.delete(items[self.sel])
            return True
        if k == Qt.Key.Key_Tab:
            keys = [c[0] for c in CATEGORIES]
            self.set_cat(keys[(keys.index(self.category) + 1) % len(keys)])
            return True
        return False

    def _ensure(self):
        cur, tgt = self.isl.scrolls.get("clip", (0.0, 0.0))
        top = self.sel * ROW
        h = CONTENT_H - 80
        if top < tgt:
            tgt = top
        elif top + ROW > tgt + h:
            tgt = top + ROW - h
        self.isl.scrolls["clip"] = (cur, tgt)

    # ------------------------------------------------------------------ dessin
    def paint(self, ui, cr):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        ui.field(QRectF(x0, cr.top(), x1 - x0, 32), "clip_search",
                 "Rechercher dans l'historique…   (Ctrl+Alt+V)", glyph=G["search"], on_change=self._reset,
                 on_submit=lambda t: (isl.paste_item(self.items()[self.sel]) if self.items() else None) or False)
        x, y = x0, cr.top() + 40
        for key, label in CATEGORIES:
            w = ui.chip_w(label)
            ui.chip(QRectF(x, y, w, 24), label, key == self.category, lambda k=key: self.set_cat(k))
            x += w + 4
        lr = QRectF(cr.left() + 8, cr.top() + 72, cr.width() - 16, cr.height() - 80)
        items = self.items()
        if not items:
            ui.empty(lr, G["clip"], "Aucun résultat" if isl.fields.get("clip_search") else "L'historique est vide",
                     "Tout ce que vous copiez apparaît ici · Entrée = coller")
            return

        def draw(y0):
            first = max(0, int((lr.top() - y0) // ROW))
            last = min(len(items), first + int(lr.height() // ROW) + 2)
            for i in range(first, last):
                self.row(ui, QRectF(lr.left(), y0 + i * ROW + 2, lr.width() - 8, ROW - 4), items[i], i)
            return len(items) * ROW
        ui.scroll("clip", lr, draw)

    def thumb(self, item):
        name = item.get("image")
        if name not in self.thumbs:
            img = QImage(self.isl.clip.image_path(item))
            pm = None
            if not img.isNull():
                side = min(img.width(), img.height())
                img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
                pm = QPixmap.fromImage(img.scaled(72, 72, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
            self.thumbs[name] = pm
        return self.thumbs[name]

    def row(self, ui, row, it, i):
        isl = self.isl
        hov = ui.row_hover(row)
        sel = isl.focus_field == "clip_search" and i == self.sel
        if hov or sel:
            ui.rect(row, T.layer2 if sel else T.hover, 6)
        if sel:
            ui.rect(QRectF(row.left(), row.top() + 12, 3, row.height() - 24), T.accent, 1.5)
        ui.row_hit(row, lambda: isl.paste_item(it))
        kind = it["kind"]
        ib = QRectF(row.left() + 10, row.top() + 6, 34, 34)
        if kind == "image":
            pm = self.thumb(it)
            clip = QPainterPath()
            clip.addRoundedRect(ib, 4, 4)
            ui.p.save()
            ui.p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
            if pm:
                ui.p.drawPixmap(ib.toRect(), pm)
            else:
                ui.p.fillRect(ib, T.layer2)
            ui.p.restore()
        else:
            g, col = {"link": (G["link"], T.accent), "email": (G["mail"], T.success), "phone": (G["phone"], T.success),
                      "files": (G["folder"], T.caution)}.get(kind, (G["doc"], T.text2))
            ui.rect(ib, T.tint(col, 40), 4)
            ui.glyph(ib.center(), g, 14, col)
        tx = row.left() + 54
        tw = row.right() - tx - (96 if hov else 12)
        if kind == "files":
            names = [os.path.basename(f) or f for f in it["files"]]
            title = names[0] + (f"  (+{len(names) - 1})" if len(names) > 1 else "")
        else:
            title = " ".join(it.get("text", "").split())
        ui.text(QRectF(tx, row.top() + 6, tw, 18), title, font(9, W.Medium))
        sub = KIND_LABEL.get(kind, "") + " · " + ago(it["time"])
        if it.get("tags"):
            sub += " · contient " + ", ".join(it["tags"])
        sx = tx
        if it.get("pinned"):
            ui.glyph(QPointF(tx + 6, row.top() + 33), G["pinned"], 10, T.orange)
            sx += 16
        ui.text(QRectF(sx, row.top() + 25, tw - (sx - tx), 16), sub, font(7.5), T.text2)
        if hov:
            bx = row.right() - 18
            for g, fn, col in ((G["delete"], lambda: isl.clip.delete(it), T.critical),
                               (G["pinned"] if it.get("pinned") else G["pin"], lambda: isl.clip.toggle_pin(it),
                                T.orange if it.get("pinned") else None),
                               (G["copy"], lambda: isl.copy_item(it), None)):
                ui.icon_button(QPointF(bx, row.center().y()), g, fn, 12, col, 28)
                bx -= 30
