"""Island input handling: hotkeys, mouse, wheel, keyboard and file drag & drop."""
import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QDrag, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from dynamic_island.core.localization import translate as tr
from dynamic_island.services import system
from dynamic_island.ui.components.drawing import LEFT
from dynamic_island.ui.themes import G, T, W, font
from dynamic_island.ui.windows.layout import COMPACT_MODES, HOTKEY_ID, HOTKEY_LAUNCH

user32 = ctypes.windll.user32


class IslandInput:
    """Mixin for Island: translate user input into island actions."""

    def nativeEvent(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                if self.is_open and self.tab == "clip":
                    self.close_island()
                else:
                    self.open_clipboard()
                return True, 0
            if msg.message == 0x0312 and msg.wParam == HOTKEY_LAUNCH:
                if self.is_open and self.tab == "launcher":
                    self.close_island()
                else:
                    self.tab = "launcher"
                    self.pinned = True
                    self.fields["launch_search"] = ""
                    self.focus("launch_search")
                return True, 0
        except Exception:
            pass
        return False, 0

    def changeEvent(self, e):
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and self.focus_field:
            self.focus_field = None
            system.set_exstyle(self.hwnd, system.WS_EX_NOACTIVATE, True)
        super().changeEvent(e)

    def mousePressEvent(self, e):
        pos = QPointF(e.position())
        dock_r, dock_items = self.dock_layout()
        if dock_r is not None and self.dock_alpha > 0.5 and dock_r.contains(pos):
            for rr, g in dock_items:
                if rr.contains(pos):
                    if g is None:  # “+N”: all applications in the launcher
                        self.tab = "launcher"
                        self.tabs["launcher"].set_view("running")
                        self.pinned = True
                    elif e.button() == Qt.MouseButton.RightButton:
                        self.dock_menu(g)
                    else:
                        self.dock_activate(g)
                    self.update()
            return
        if not self.pill_rect().contains(pos):
            return
        if e.button() == Qt.MouseButton.RightButton:
            self.tray_menu.popup(QCursor.pos())
            return
        for hit, setter, _v, track in reversed(self.sliders):
            if hit.contains(pos):
                self.drag = (track, setter)
                self._drag_to(pos)
                return
        for rect, fn in reversed(self.hits):
            if rect.contains(pos):
                fn()
                self.update()
                return
        for rect, paths, click in reversed(self.draggables):
            if rect.contains(pos):
                self._press = (pos, paths, click)  # click or drag decided on move/release
                return
        if self.focus_field:
            self.unfocus(restore=False)
        if self.mode == "alert":
            self.open_alert()
            return
        if self.mode in COMPACT_MODES:
            self.tab = {"cmedia": "home", "ctimer": "timers", "cmeet": "agenda", "cbuild": "dev"}.get(self.mode, self.tab)
            self.pinned = True
            if hasattr(self, "pin_action"):
                self.pin_action.setChecked(True)

    def _drag_to(self, pos):
        rect, setter = self.drag
        setter(max(0.0, min(1.0, (pos.x() - rect.left()) / rect.width())))

    def mouseMoveEvent(self, e):
        if self.drag:
            self._drag_to(QPointF(e.position()))
        elif self._press:
            pos, paths, _click = self._press
            if (QPointF(e.position()) - pos).manhattanLength() > 8:
                self._press = None
                self.start_file_drag(paths)

    def mouseReleaseEvent(self, e):
        if self.drag:
            self.drag = None
            self.refresh_visible()
        if self._press:
            _pos, _paths, click = self._press
            self._press = None
            click()

    def start_file_drag(self, paths):
        """Drag files from the island to another application (Explorer, email, browser…)."""
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        drag = QDrag(self)
        drag.setMimeData(md)
        pm = QPixmap(220, 36)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setBrush(QColor(0, 0, 0, 230))
        q.setPen(QPen(T.stroke2, 1))
        q.drawRoundedRect(QRectF(0.5, 0.5, 219, 35), 6, 6)
        q.setPen(T.text)
        q.setFont(font(9, W.Medium))
        name = os.path.basename(paths[0]) + (f"  +{len(paths) - 1}" if len(paths) > 1 else "")
        q.drawText(QRectF(12, 0, 200, 36), int(LEFT), name)
        q.end()
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        self.drag_out = True
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, Qt.DropAction.CopyAction)
        self.drag_out = False
        self.files.changed.emit()

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if self.drag_out or not md.hasUrls() or not any(u.isLocalFile() for u in md.urls()):
            e.ignore()
            return
        e.acceptProposedAction()
        self.drop_hover = True
        self.tab = "files"
        self.tabs["files"].set_view("shelf")

    def dragMoveEvent(self, e):
        if self.drop_hover:
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.drop_hover = False

    def dropEvent(self, e):
        self.drop_hover = False
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        n = self.files.add_to_shelf(paths)
        e.acceptProposedAction()
        self.pinned = True
        title = (tr("island.files.pending", count=n) if n
                 else tr("island.files.already_on_shelf"))
        self.show_alert("files", title, os.path.basename(paths[0]) if paths else "",
                        T.accent, G["folder"])

    def copy_files(self, paths):
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QApplication.clipboard().setMimeData(md)
        self.show_alert("files", tr("island.files.copied", count=len(paths)),
                        tr("island.files.paste_hint"), T.accent, G["copy"], duration=2)

    def wheelEvent(self, e):
        pos = QPointF(e.position())
        steps = e.angleDelta().y() / 120
        for hit, setter, val, _t in reversed(self.sliders):
            if hit.contains(pos):
                setter(max(0.0, min(1.0, val + steps * 0.04)))
                return
        for rect, key, mx in reversed(self.scroll_regions):
            if rect.contains(pos):
                cur, tgt = self.scrolls.get(key, (0.0, 0.0))
                self.scrolls[key] = (cur, max(0.0, min(mx, tgt - steps * 60)))
                return
        if self.mode in COMPACT_MODES:
            self.audio.set_volume(self.audio.volume() + steps * 0.04)

    def keyPressEvent(self, e):
        name = self.focus_field
        if not name:
            return
        tab = self.tabs.get(self.tab)
        if name in ("clip_search", "launch_search") and hasattr(tab, "key_event") and e.key() != Qt.Key.Key_Escape \
                and tab.key_event(e):
            self.update()
            return
        k = e.key()
        mods = e.modifiers()
        val = self.fields.get(name, "")
        on_submit, on_change = self.field_handlers.get(name, (None, None))
        changed = False
        if k == Qt.Key.Key_Escape:
            if val:
                self.fields[name] = ""
                changed = True
            else:
                self.unfocus()
                if self.pinned and not self.hovered:
                    self.close_island()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if on_submit and val.strip():
                if on_submit(val):
                    self.fields[name] = ""
                    changed = True
        elif k == Qt.Key.Key_Backspace:
            if mods & Qt.KeyboardModifier.ControlModifier:
                v = val.rstrip()
                self.fields[name] = v[: max(0, v.rfind(" ") + 1)]
            else:
                self.fields[name] = val[:-1]
            changed = True
        elif k == Qt.Key.Key_V and mods & Qt.KeyboardModifier.ControlModifier:
            txt = QApplication.clipboard().text()
            if name != "note_add":
                txt = " ".join(txt.split())
            self.fields[name] = val + txt
            changed = True
        elif e.text() and e.text().isprintable() and not (mods & Qt.KeyboardModifier.ControlModifier):
            self.fields[name] = val + e.text()
            changed = True
        if changed and on_change:
            on_change(self.fields.get(name, ""))
        self.update()
