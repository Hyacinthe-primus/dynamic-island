"""Onglet Lanceur : recherche d'applications, favoris, groupes, applis récentes,
raccourcis personnalisés, PowerShell, scripts Python."""
import re
import time
import webbrowser

from PySide6.QtCore import QPointF, QRectF, Qt

from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT

CONTENT_H = 372
STOP, MINI, APP, APPS = chr(0xE71A), chr(0xE921), chr(0xE71D), chr(0xE7C4)
KIND = {"app": "Application", "uwp": "Application Store", "url": "Site web", "folder": "Dossier", "file": "Fichier",
        "ps": "PowerShell", "py": "Script Python"}
KIND_G = {"url": G["globe"], "folder": G["folder"], "file": G["doc"], "ps": G["terminal"], "py": G["code"],
          "uwp": "\uE71D", "app": "\uE71D"}


class LauncherTab:
    key, label, glyph = "launcher", "Lanceur", "\uE8FC"

    def __init__(self, isl):
        self.isl = isl
        self.sel = 0
        self.view = "home"
        self.confirm_kill = None

    def height(self):
        return CONTENT_H

    # ------------------------------------------------------------------ saisie
    def results(self):
        q = self.isl.fields.get("launch_search", "").strip()
        if not q or q.startswith(("+", ">", "ps:", "py:")):
            return []
        return self.isl.launcher.search(q, 10)

    def set_view(self, v):
        self.view = v
        self.sel = 0
        self.isl.launcher.running_visible = v == "running"
        if v == "running":
            self.isl.launcher.refresh_running()

    def running_filtered(self):
        q = self.isl.fields.get("launch_search", "").strip().lower()
        apps = self.isl.launcher.running
        if not q:
            return apps
        return [g for g in apps if q in g["name"].lower() or any(q in w["title"].lower() for w in g["windows"])]

    def _submit(self, text):
        L = self.isl.launcher
        t = text.strip()
        if self.view == "running":
            apps = self.running_filtered()
            if apps:
                self.show(apps[min(self.sel, len(apps) - 1)]["windows"][0]["hwnd"])
                return True
            return False
        low = t.lower()
        if t.startswith("+"):
            r = L.parse_add(t)
            self.isl.show_alert("launch", "Ajouté au lanceur" if r else "Ajout impossible",
                                (r or {}).get("name", t), T.success if r else T.critical, G["add"])
            return r is not None
        if t.startswith(">") or low.startswith("ps:"):
            L.run_powershell(re.sub(r"^(ps:|>)\s*", "", t, flags=re.I))
            return True
        if low.startswith("py:"):
            L.launch({"name": t, "target": t, "kind": "py"})
            return True
        if re.match(r"^(https?://|www\.)\S+$", t) or re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", t) and " " not in t:
            webbrowser.open(t if t.startswith("http") else "https://" + t)
            self.isl.close_island(restore_focus=False)
            return True
        res = self.results()
        if res:
            self.run(res[min(self.sel, len(res) - 1)])
            return True
        return False

    def key_event(self, e):
        res = self.running_filtered() if self.view == "running" else self.results()
        if e.key() == Qt.Key.Key_Down and res:
            self.sel = min(len(res) - 1, self.sel + 1)
            return True
        if e.key() == Qt.Key.Key_Up and res:
            self.sel = max(0, self.sel - 1)
            return True
        return False

    def run(self, it):
        if self.isl.launcher.launch(it):
            if it.get("kind") != "ps":
                self.isl.close_island(restore_focus=False)
            self.isl.fields["launch_search"] = ""

    # ------------------------------------------------------------------ dessin
    def paint(self, ui, cr):
        isl = self.isl
        x0, x1 = cr.left() + 16, cr.right() - 16
        ph = ("Filtrer les applications ouvertes · Entrée pour afficher" if self.view == "running" else
              "Rechercher une app (Ctrl+Alt+Espace) · + Nom = cible · > commande · py: script.py · site.com")
        ui.field(QRectF(x0, cr.top(), x1 - x0, 32), "launch_search", ph,
                 on_submit=self._submit, glyph=G["search"], on_change=lambda *_: setattr(self, "sel", 0))
        n = len(isl.launcher.running)
        ui.segmented(QRectF(x0 - 6, cr.top() + 38, 0, 28),
                     [("home", "Lancer"), ("running", f"En cours ({n})" if n else "En cours")], self.view, self.set_view)
        body = QRectF(cr.left() + 8, cr.top() + 72, cr.width() - 16, cr.height() - 78)
        q = isl.fields.get("launch_search", "").strip()
        if self.view == "running":
            self._running(ui, body)
        elif q:
            self._search(ui, body, q)
        else:
            ui.scroll("launcher", body, lambda y: self._home(ui, body, y))

    # ------------------------------------------------------------------ applications en cours
    def show(self, hwnd):
        self.isl.close_island(restore_focus=False)
        self.isl.launcher.show_window(hwnd)

    def _kill(self, g):
        c = self.confirm_kill
        if c and c[0] == g["key"] and time.time() - c[1] < 3:
            self.confirm_kill = None
            self.isl.launcher.kill_app(g)
            self.isl.show_alert("launch", f"{g['name']} arrêté", "Fermeture forcée", T.critical, STOP)
        else:
            self.confirm_kill = (g["key"], time.time())

    def _running(self, ui, body):
        L = self.isl.launcher
        apps = self.running_filtered()
        if not apps:
            ui.empty(body, APPS, "Aucune application ouverte" if not L.running else "Aucun résultat",
                     "Les fenêtres ouvertes apparaissent ici")
            return

        def draw(y0):
            x0, x1 = body.left() + 4, body.right() - 12
            y = y0
            for i, g in enumerate(apps):
                r = QRectF(x0, y, x1 - x0, 46)
                nw = len(g["windows"])
                if ui.visible(r):
                    hov = ui.row_hover(r)
                    sel = i == self.sel and self.isl.focus_field == "launch_search"
                    ui.rect(r, T.layer2 if (hov or sel) else T.layer, 6, T.stroke)
                    if sel:
                        ui.rect(QRectF(r.left(), r.top() + 13, 3, 20), T.accent, 1.5)
                    ui.file_icon(QRectF(r.left() + 12, r.top() + 10, 26, 26), g["exe"], APP)
                    confirm = bool(self.confirm_kill and self.confirm_kill[0] == g["key"]
                                   and time.time() - self.confirm_kill[1] < 3)
                    right = 136 if (hov or confirm) else 70
                    ui.text(QRectF(r.left() + 48, r.top() + 5, r.width() - 56 - right, 18), g["name"], font(9.5, W.DemiBold))
                    sub = g["windows"][0]["title"] if nw == 1 else f"{nw} fenêtres"
                    ui.text(QRectF(r.left() + 48, r.top() + 24, r.width() - 56 - right, 16), sub, font(7.5), T.text3)
                    ui.row_hit(QRectF(r.left(), r.top(), r.width() - right, r.height()),
                               lambda h=g["windows"][0]["hwnd"]: self.show(h))
                    if confirm:
                        ui.button(QRectF(r.right() - 132, r.top() + 9, 122, 28), "Forcer l'arrêt ?",
                                  lambda g=g: self._kill(g), STOP, accent=True)
                    elif hov:
                        bx = r.right() - 18
                        for g_, fn, col in ((STOP, lambda g=g: self._kill(g), T.critical),
                                            (G["close"], lambda g=g: L.close_app(g), None),
                                            (MINI, lambda g=g: [L.minimize_window(w["hwnd"]) for w in g["windows"]], None),
                                            (G["open"], lambda h=g["windows"][0]["hwnd"]: self.show(h), None)):
                            ui.icon_button(QPointF(bx, r.center().y()), g_, fn, 11, col, 26)
                            bx -= 30
                    else:
                        ui.text(QRectF(r.right() - 76, r.top(), 66, 46), f"{g['mem'] / 2 ** 20:.0f} Mo", font(7.5),
                                T.text3, RIGHT)
                y += 50
                if nw > 1:  # chaque fenêtre de l'appli (fenêtres de navigateur, documents…)
                    for wnd in g["windows"]:
                        wr = QRectF(x0 + 30, y, x1 - x0 - 30, 28)
                        if ui.visible(wr):
                            hov = ui.row_hover(wr)
                            if hov:
                                ui.rect(wr, T.hover, 4)
                            ui.rect(QRectF(wr.left() - 12, wr.top() + 13, 6, 1.5), T.stroke2, 0)
                            ui.text(QRectF(wr.left() + 4, wr.top(), wr.width() - (100 if hov else 70), 28), wnd["title"],
                                    font(8), T.text3 if wnd["min"] else T.text2)
                            if wnd["min"] and not hov:
                                ui.badge(wr.right() - 64, wr.top() + 6, "réduite", T.text3)
                            ui.row_hit(QRectF(wr.left(), wr.top(), wr.width() - (90 if hov else 0), wr.height()),
                                       lambda h=wnd["hwnd"]: self.show(h))
                            if hov:
                                bx = wr.right() - 14
                                for g_, fn in ((G["close"], lambda h=wnd["hwnd"]: L.close_window(h)),
                                               (MINI, lambda h=wnd["hwnd"]: L.minimize_window(h)),
                                               (G["open"], lambda h=wnd["hwnd"]: self.show(h))):
                                    ui.icon_button(QPointF(bx, wr.center().y()), g_, fn, 10, None, 22)
                                    bx -= 26
                        y += 30
                    y += 4
            ui.text(QRectF(x0, y + 2, x1 - x0, 16), "Croix : fermeture normale (l'appli peut proposer d'enregistrer) · "
                                                    "carré rouge : arrêt forcé (2 clics)", font(7), T.text3)
            return y - y0 + 22
        ui.scroll("running", body, draw)

    def _icon(self, ui, rect, it):
        if it.get("kind") in ("app", "folder", "file") or (it.get("kind") == "py" and not it["target"].lower().startswith("py:")):
            ui.file_icon(rect, it["target"], KIND_G.get(it.get("kind")))
        else:
            ui.rect(rect, T.tint(T.accent, 40), 6)
            ui.glyph(rect.center(), KIND_G.get(it.get("kind"), "\uE71D"), rect.height() * 0.5, T.accent)

    def _search(self, ui, body, q):
        L = self.isl.launcher
        y = body.top()
        x0, x1 = body.left() + 8, body.right() - 8
        if q.startswith("+"):
            ui.wrap(QRectF(x0, y, x1 - x0, 80),
                    "Entrée pour ajouter. Exemples : « + GitHub = https://github.com », « + Notes = notepad.exe "
                    "C:\\notes.txt », « + Projets = D:\\Code », « + Disque = ps: Get-PSDrive C », « + Backup = py: "
                    "C:\\scripts\\backup.py », « + groupe Travail : Visual Studio Code, Microsoft Edge, Spotify ».",
                    font(8.5), T.text2, 4)
            return
        if q.startswith(">") or q.lower().startswith("ps:"):
            ui.text(QRectF(x0, y, x1 - x0, 20), "Entrée pour exécuter dans PowerShell :", font(8.5), T.text2)
            ui.text(QRectF(x0, y + 22, x1 - x0, 20), re.sub(r"^(ps:|>)\s*", "", q, flags=re.I), font(9, W.DemiBold))
            self._output(ui, QRectF(x0, y + 52, x1 - x0, body.bottom() - y - 52))
            return
        res = self.results()
        if not res:
            ui.empty(body, G["search"], "Aucune application trouvée",
                     "Entrée ouvre l'adresse si c'est un site · « + » pour créer un raccourci")
            return
        favs = {i["target"] for i in L.items}
        for i, it in enumerate(res):
            r = QRectF(body.left(), y, body.width(), 38)
            sel = i == self.sel
            hov = ui.hovering(r)
            if sel or hov:
                ui.rect(r, T.layer2 if sel else T.hover, 6)
            if sel:
                ui.rect(QRectF(r.left(), r.top() + 10, 3, 18), T.accent, 1.5)
            self._icon(ui, QRectF(r.left() + 12, r.top() + 7, 24, 24), it)
            ui.text(QRectF(r.left() + 46, r.top(), r.width() - 180, 38), it["name"], font(9.5, W.Medium))
            ui.text(QRectF(r.right() - 170, r.top(), 120, 38), KIND.get(it.get("kind"), ""), font(7.5), T.text3, RIGHT)
            ui.hit(r, lambda it=it: self.run(it))
            fav = it["target"] in favs
            ui.icon_button(QPointF(r.right() - 22, r.center().y()), G["star_on"] if fav else G["star"],
                           (lambda it=it: L.add_app_favorite(it)) if not fav else (lambda: None), 12,
                           T.caution if fav else None, 26)
            y += 40

    def _home(self, ui, body, y0):
        L = self.isl.launcher
        x0, x1 = body.left() + 8, body.right() - 12
        y = y0
        # favoris
        ui.section(x0, y, x1 - x0, "Favoris", "+ Ajouter", lambda: self._prefill("+ "))
        y += 24
        items = L.items
        if not items:
            ui.text(QRectF(x0, y, x1 - x0, 18), "Cherchez une app puis cliquez sur l'étoile, ou tapez « + Nom = cible »", font(8), T.text3)
            y += 26
        cols, gap = 7, 6
        cw = (x1 - x0 - gap * (cols - 1)) / cols
        for i, it in enumerate(items):
            r = QRectF(x0 + (i % cols) * (cw + gap), y + (i // cols) * 74, cw, 68)
            if ui.visible(r):
                hov = ui.row_hover(r)
                ui.rect(r, T.layer2 if hov else T.layer, 6, T.stroke)
                self._icon(ui, QRectF(r.center().x() - 14, r.top() + 9, 28, 28), it)
                ui.text(QRectF(r.left() + 4, r.top() + 42, r.width() - 8, 18), it["name"], font(7.5), T.text, CENTER)
                ui.row_hit(r, lambda it=it: self.run(it))
                if hov:
                    ui.icon_button(QPointF(r.right() - 10, r.top() + 10), G["close"], lambda it=it: L.remove_item(it), 8,
                                   None, 18)
        if items:
            y += ((len(items) - 1) // cols + 1) * 74 + 4
        # groupes
        ui.section(x0, y, x1 - x0, "Groupes d'applications", "+ Créer", lambda: self._prefill("+ groupe "))
        y += 24
        if not L.groups:
            ui.text(QRectF(x0, y, x1 - x0, 18), "« + groupe Travail : Code, Edge, Spotify » lance tout en un clic",
                    font(8), T.text3)
            y += 26
        by = {i["id"]: i for i in items}
        for g in L.groups:
            r = QRectF(x0, y, x1 - x0, 36)
            if ui.visible(r):
                hov = ui.row_hover(r)
                ui.card(r)
                ui.glyph(QPointF(r.left() + 18, r.center().y()), "\uE8A9", 13, T.accent)
                ui.text(QRectF(r.left() + 36, r.top(), 140, 36), g["name"], font(9, W.DemiBold))
                x = r.left() + 180
                for iid in g["items"][:8]:
                    if iid in by:
                        self._icon(ui, QRectF(x, r.top() + 8, 20, 20), by[iid])
                        x += 24
                ui.button(QRectF(r.right() - 104, r.top() + 5, 70, 26), "Lancer",
                          lambda g=g: (L.run_group(g), self.isl.close_island(restore_focus=False)), G["play"], accent=True)
                ui.icon_button(QPointF(r.right() - 16, r.center().y()), G["delete"], lambda g=g: L.remove_group(g), 11,
                               T.critical, 24)
            y += 40
        # récents
        y += 4
        ui.section(x0, y, x1 - x0, "Récemment utilisées")
        y += 24
        rec = L.recent_apps[:7]
        if not rec:
            ui.text(QRectF(x0, y, x1 - x0, 18), "Chargement…", font(8), T.text3)
            y += 24
        for i, it in enumerate(rec):
            r = QRectF(x0 + i * (cw + gap), y, cw, 68)
            if ui.visible(r):
                hov = ui.row_hover(r)
                ui.rect(r, T.layer2 if hov else T.layer, 6, T.stroke)
                self._icon(ui, QRectF(r.center().x() - 14, r.top() + 9, 28, 28), it)
                ui.text(QRectF(r.left() + 4, r.top() + 42, r.width() - 8, 18), it["name"], font(7.5), T.text, CENTER)
                ui.row_hit(r, lambda it=it: self.run(it))
        if rec:
            y += 76
        if L.last_output:
            y += 4
            y += self._output(ui, QRectF(x0, y, x1 - x0, 140))
        return y - y0 + 6

    def _output(self, ui, r):
        o = self.isl.launcher.last_output
        if not o:
            return 0
        ui.card(r)
        col = T.caution if o["ok"] is None else (T.success if o["ok"] else T.critical)
        ui.glyph(QPointF(r.left() + 16, r.top() + 15), G["terminal"], 11, col)
        ui.text(QRectF(r.left() + 30, r.top() + 4, r.width() - 110, 22), "PS> " + o["cmd"], font(8, W.DemiBold))
        ui.icon_button(QPointF(r.right() - 44, r.top() + 15), G["copy"], lambda: self.isl.copy_text(o["out"]), 10, None, 22)
        ui.icon_button(QPointF(r.right() - 18, r.top() + 15), G["close"],
                       lambda: setattr(self.isl.launcher, "last_output", None), 10, None, 22)
        lines = o["out"].splitlines()[-int((r.height() - 34) // 15):]
        f = font(7.5)
        for i, l in enumerate(lines):
            ui.text(QRectF(r.left() + 12, r.top() + 28 + i * 15, r.width() - 24, 15), l, f, T.text2)
        return r.height() + 6

    def _prefill(self, txt):
        self.isl.fields["launch_search"] = txt
        self.isl.focus("launch_search")
