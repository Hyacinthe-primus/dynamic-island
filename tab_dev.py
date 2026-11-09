"""Onglet Dev : projet ouvert, Git, GitHub, builds/CI/Jenkins/logs, serveurs locaux, projets favoris."""
import os
import time

from PySide6.QtCore import QPointF, QRectF

from store import settings
from theme import G, T, W, font
from ui import CENTER, LEFT, RIGHT, ago

CONTENT_H = 372
VIEWS = [("git", "Git"), ("github", "GitHub"), ("builds", "Builds"), ("servers", "Serveurs"), ("projects", "Projets")]


class DevTab:
    key, label, glyph = "dev", "Dev", G["code"]

    def __init__(self, isl):
        self.isl = isl
        self.view = "git"
        self.confirm_kill = None

    def height(self):
        return CONTENT_H

    def set_view(self, v):
        self.view = v
        self.isl.dev.refresh()

    def paint(self, ui, cr):
        dev = self.isl.dev
        x0, x1 = cr.left() + 16, cr.right() - 16
        y = cr.top()
        # ---- carte projet
        r = QRectF(x0, y, x1 - x0, 62)
        ui.card(r)
        pj = dev.project
        if pj:
            ui.glyph(QPointF(r.left() + 20, r.top() + 20), G["code"], 15, T.accent)
            ui.text(QRectF(r.left() + 38, r.top() + 6, 220, 20), pj["name"], font(10.5, W.DemiBold))
            ui.text(QRectF(r.left() + 38, r.top() + 25, 240, 16), (pj.get("ide") or "") + (" · " + pj["path"] if pj.get("path") else
                                                                                         " · dossier inconnu"), font(7.5), T.text3)
            g = dev.git
            x = r.left() + 38
            if g and g.get("branch"):
                ui.glyph(QPointF(x + 5, r.top() + 50), G["branch"], 10, T.text2)
                ui.text(QRectF(x + 13, r.top() + 42, 120, 16), g["branch"], font(8, W.DemiBold), T.text)
                x += 20 + ui.tw(g["branch"], font(8, W.DemiBold)) + 6
                st = {"clean": ("Propre", T.success), "modified": ("Modifié", T.orange),
                      "uncommitted": ("Non commité", T.caution)}[g["status"]]
                x += ui.badge(x, r.top() + 42, st[0], st[1]) + 5
                if g["changes"]:
                    x += ui.badge(x, r.top() + 42, f"{g['changes']} fichier(s)", T.text2) + 5
                if g["ahead"]:
                    x += ui.badge(x, r.top() + 42, f"↑{g['ahead']}", T.accent) + 5
                if g["behind"]:
                    x += ui.badge(x, r.top() + 42, f"↓{g['behind']}", T.purple) + 5
            elif g and g.get("error"):
                ui.text(QRectF(x, r.top() + 42, 200, 16), g["error"], font(7.5), T.text3)
            bx = r.right() - 8
            for g_, tip, fn in ((G["terminal"], "Terminal", dev.open_terminal), (G["folder"], "Dossier", dev.open_folder),
                                (G["open"], "Ouvrir", dev.open_project), (G["build"], "Build", dev.start_build)):
                ui.icon_button(QPointF(bx - 16, r.top() + 20), g_, fn, 13, size=30)
                bx -= 32
            if dev.git and dev.git.get("repo"):
                ui.icon_button(QPointF(bx - 16, r.top() + 20), G["github"],
                               lambda: self.isl.open_url("https://github.com/" + dev.git["repo"]), 13, size=30)
        else:
            ui.glyph(QPointF(r.left() + 20, r.center().y()), G["code"], 15, T.text3)
            ui.text(QRectF(r.left() + 38, r.top() + 10, r.width() - 50, 20), "Aucun IDE détecté", font(10, W.DemiBold))
            ui.text(QRectF(r.left() + 38, r.top() + 30, r.width() - 50, 18),
                    "Ouvrez VS Code, IntelliJ, PyCharm, Visual Studio… ou choisissez un projet dans « Projets »",
                    font(7.5), T.text3)
        y += 68
        ui.segmented(QRectF(x0 - 6, y, 0, 28), VIEWS, self.view, self.set_view)
        body = QRectF(cr.left() + 8, y + 34, cr.width() - 16, cr.bottom() - y - 40)
        getattr(self, "_" + self.view)(ui, body)

    # ------------------------------------------------------------------ git
    def _git(self, ui, body):
        g = self.isl.dev.git
        if not g or not g.get("branch"):
            ui.empty(body, G["branch"], "Pas de dépôt Git pour ce projet")
            return

        def draw(y0):
            x0, x1 = body.left() + 8, body.right() - 14
            y = y0
            ui.text(QRectF(x0, y, 200, 18), "Commits récents", font(8.5, W.DemiBold))
            y += 22
            for h, msg, when, author in g["commits"]:
                ui.text(QRectF(x0, y, 60, 22), h, font(8, W.DemiBold), T.accent)
                ui.text(QRectF(x0 + 62, y, x1 - x0 - 200, 22), msg, font(8.5))
                ui.text(QRectF(x1 - 136, y, 136, 22), f"{author} · {when}", font(7.5), T.text3, RIGHT)
                y += 24
            if not g["commits"]:
                ui.text(QRectF(x0, y, 300, 20), "Aucun commit", font(8.5), T.text3)
                y += 22
            y += 8
            ui.text(QRectF(x0, y, 300, 18), f"Modifications ({g['changes']}) — {g['staged']} indexé(s), "
                                            f"{g['modified']} modifié(s), {g['untracked']} nouveau(x)", font(8.5, W.DemiBold))
            y += 22
            for f in g["files"]:
                code, path = f[:2], f[3:]
                col = T.success if code.strip() in ("A", "??") else (T.critical if "D" in code else T.orange)
                ui.text(QRectF(x0, y, 26, 20), code.replace(" ", "·"), font(8, W.DemiBold), col)
                ui.text(QRectF(x0 + 30, y, x1 - x0 - 30, 20), path, font(8), T.text2)
                y += 20
            return y - y0 + 6
        ui.scroll("dev_git", body, draw)

    # ------------------------------------------------------------------ github
    def _github(self, ui, body):
        dev = self.isl.dev
        x0, x1 = body.left() + 8, body.right() - 14
        has_tok = bool(settings.get("github_token"))
        if not has_tok:
            ui.field(QRectF(x0, body.top(), x1 - x0, 30), "gh_token",
                     "Jeton GitHub (facultatif : notifications + dépôts privés) puis Entrée",
                     on_submit=lambda t: dev.set_token(t) or True, glyph=G["lock"], secret=True)
            body = QRectF(body.left(), body.top() + 36, body.width(), body.height() - 36)
        if not dev.git or not dev.git.get("repo"):
            ui.empty(body, G["github"], "Aucun dépôt GitHub détecté", "Le remote « origin » doit pointer vers github.com")
            return
        gh = dev.gh
        if not gh:
            ui.empty(body, G["refresh"], "Chargement de GitHub…", dev.gh_err or dev.git["repo"])
            return

        def section(y, title, items, row):
            ui.text(QRectF(x0, y, 300, 18), f"{title} ({len(items)})", font(8.5, W.DemiBold))
            y += 22
            if not items:
                ui.text(QRectF(x0, y, 300, 18), "Rien à afficher", font(8), T.text3)
                return y + 24
            for it in items:
                rr = QRectF(x0 - 4, y, x1 - x0 + 8, 26)
                if ui.row_hover(rr):
                    ui.rect(rr, T.hover, 4)
                row(rr, it)
                if it.get("url"):
                    ui.row_hit(rr, lambda u=it["url"]: self.isl.open_url(u))
                y += 28
            return y + 6

        def run_row(rr, r):
            if r["status"] != "completed":
                g_, col, st = G["refresh"], T.caution, "en cours"
            elif r["conclusion"] == "success":
                g_, col, st = G["check"], T.success, "réussi"
            elif r["conclusion"] in ("failure", "timed_out"):
                g_, col, st = G["close"], T.critical, "échec"
            else:
                g_, col, st = G["info"], T.text3, r["conclusion"] or ""
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), g_, 11, col)
            ui.text(QRectF(rr.left() + 26, rr.top(), rr.width() - 200, 26), f"{r['name']} — {r['title']}", font(8.5))
            ui.text(QRectF(rr.right() - 170, rr.top(), 164, 26), f"{r['branch']} · {st}", font(7.5), col, RIGHT)

        def pr_row(rr, p):
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), G["branch"], 11, T.text3 if p.get("draft") else T.success)
            ui.text(QRectF(rr.left() + 26, rr.top(), rr.width() - 140, 26), f"#{p['n']} {p['title']}", font(8.5))
            ui.text(QRectF(rr.right() - 110, rr.top(), 104, 26), p["user"], font(7.5), T.text3, RIGHT)

        def issue_row(rr, i):
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), G["bug"], 11, T.orange)
            ui.text(QRectF(rr.left() + 26, rr.top(), rr.width() - 160, 26), f"#{i['n']} {i['title']}", font(8.5))
            ui.text(QRectF(rr.right() - 130, rr.top(), 124, 26), ", ".join(i["labels"]) or i["user"], font(7.5), T.text3, RIGHT)

        def dep_row(rr, d):
            col = {"success": T.success, "failure": T.critical, "error": T.critical, "in_progress": T.caution}.get(d["state"], T.text3)
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), G["rocket"], 11, col)
            ui.text(QRectF(rr.left() + 26, rr.top(), rr.width() - 160, 26), f"{d['env']} · {d['ref']}", font(8.5))
            ui.text(QRectF(rr.right() - 130, rr.top(), 124, 26), d["state"], font(7.5), col, RIGHT)
            d["url"] = d.get("url")

        def notif_row(rr, n):
            ui.glyph(QPointF(rr.left() + 12, rr.center().y()), G["bell"], 11, T.accent)
            ui.text(QRectF(rr.left() + 26, rr.top(), rr.width() - 180, 26), n["title"], font(8.5))
            ui.text(QRectF(rr.right() - 150, rr.top(), 144, 26), n["repo"].split("/")[-1] + " · " + n["reason"],
                    font(7.5), T.text3, RIGHT)

        def draw(y0):
            y = y0
            ui.text(QRectF(x0, y, 300, 18), gh["repo"], font(9, W.DemiBold), T.accent)
            ui.text(QRectF(x1 - 160, y, 160, 18), "mis à jour " + ago(gh["time"]), font(7.5), T.text3, RIGHT)
            y += 26
            y = section(y, "CI / Actions", gh["runs"][:6], run_row)
            y = section(y, "Pull requests", gh["pulls"], pr_row)
            y = section(y, "Issues", gh["issues"], issue_row)
            if gh.get("deployments"):
                y = section(y, "Déploiements", gh["deployments"], dep_row)
            if has_tok:
                y = section(y, "Notifications", gh["notifications"], notif_row)
            return y - y0
        ui.scroll("dev_gh", body, draw)

    # ------------------------------------------------------------------ builds
    def _builds(self, ui, body):
        dev = self.isl.dev

        def draw(y0):
            x0, x1 = body.left() + 8, body.right() - 14
            y = y0
            b = dev.build
            ui.text(QRectF(x0, y, 300, 22), "Build local", font(8.5, W.DemiBold))
            if b and b.get("running"):
                ui.button(QRectF(x1 - 90, y - 2, 90, 26), "Arrêter", dev.stop_build, G["stop"], danger=True)
            else:
                ui.button(QRectF(x1 - 90, y - 2, 90, 26), "Lancer", dev.start_build, G["play"], accent=True,
                          enabled=bool(dev.project and dev.project.get("path")))
            y += 30
            if b:
                if b.get("running"):
                    col, st = T.caution, f"En cours… {int(time.time() - b['start'])} s"
                elif b.get("ok"):
                    col, st = T.success, f"Réussi en {int(b['end'] - b['start'])} s"
                else:
                    col, st = T.critical, f"Échec — {len(b['errors'])} erreur(s)"
                ui.text(QRectF(x0, y, x1 - x0, 18), f"{b.get('cmd') or ''}  ·  {st}", font(8, W.DemiBold), col)
                y += 22
                lines = b["errors"][-8:] if b["errors"] else b["out"][-4:]
                for l in lines:
                    ui.text(QRectF(x0 + 6, y, x1 - x0 - 6, 18), l, font(7.5), T.critical if b["errors"] else T.text2)
                    y += 18
            else:
                ui.text(QRectF(x0, y, x1 - x0, 18), "Lance la commande détectée (npm run build, mvn compile, "
                                                    "dotnet build, php artisan test…)", font(8), T.text3)
                y += 22
            # GitHub Actions en cours
            if dev.gh:
                running = [r for r in dev.gh["runs"] if r["status"] != "completed"]
                if running:
                    y += 8
                    ui.text(QRectF(x0, y, 300, 18), "Builds CI en cours", font(8.5, W.DemiBold))
                    y += 22
                    for r in running:
                        ui.glyph(QPointF(x0 + 8, y + 10), G["refresh"], 10, T.caution)
                        ui.text(QRectF(x0 + 22, y, x1 - x0 - 22, 20), f"{r['name']} · {r['branch']}", font(8.5))
                        y += 22
            # Jenkins
            y += 8
            ui.text(QRectF(x0, y, 300, 18), "Jenkins", font(8.5, W.DemiBold))
            y += 22
            jk = dev.jenkins
            if not settings.get("jenkins", {}).get("url"):
                ui.field(QRectF(x0, y, x1 - x0, 30), "jenkins_url",
                         "URL Jenkins [utilisateur jeton] — ex : http://localhost:8080 admin 11ab…",
                         on_submit=self._set_jenkins, glyph=G["server"])
                y += 38
            elif jk and jk.get("error"):
                ui.text(QRectF(x0, y, x1 - x0, 18), jk["error"], font(8), T.critical)
                y += 22
            elif jk:
                for j in jk["jobs"][:10]:
                    c = j["color"]
                    col = T.success if c.startswith("blue") else (T.critical if c.startswith("red") else
                                                                  (T.caution if c.startswith("yellow") else T.text3))
                    ui.glyph(QPointF(x0 + 8, y + 10), G["refresh"] if j["building"] else G["build"], 10, col)
                    ui.text(QRectF(x0 + 22, y, x1 - x0 - 150, 20), j["name"], font(8.5))
                    ui.text(QRectF(x1 - 130, y, 130, 20), ("en cours" if j["building"] else (j["result"] or "—").lower())
                            + (f" · #{j['number']}" if j["number"] else ""), font(7.5), col, RIGHT)
                    y += 22
            # logs
            y += 8
            ui.text(QRectF(x0, y, 300, 18), "Logs importants du projet", font(8.5, W.DemiBold))
            y += 22
            if not dev.logs:
                ui.text(QRectF(x0, y, x1 - x0, 18), "Aucune erreur dans les fichiers .log du projet", font(8), T.text3)
                y += 22
            for lg in dev.logs[:12]:
                ui.text(QRectF(x0, y, 110, 18), lg["file"], font(7.5, W.DemiBold), T.text3)
                ui.text(QRectF(x0 + 112, y, x1 - x0 - 112, 18), lg["line"], font(7.5), T.critical)
                y += 18
            return y - y0 + 8
        ui.scroll("dev_builds", body, draw)

    def _set_jenkins(self, text):
        parts = text.split()
        if not parts or not parts[0].startswith("http"):
            return False
        self.isl.dev.set_jenkins(parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else "")
        return True

    # ------------------------------------------------------------------ serveurs
    def _servers(self, ui, body):
        dev = self.isl.dev

        def draw(y0):
            x0, x1 = body.left() + 8, body.right() - 14
            y = y0
            ports = [p for p in dev.ports if p["dev"]] or dev.ports[:8]
            ui.text(QRectF(x0, y, 300, 18), f"Serveurs locaux actifs ({len(ports)})", font(8.5, W.DemiBold))
            y += 22
            for p in ports:
                rr = QRectF(x0 - 4, y, x1 - x0 + 8, 30)
                if ui.row_hover(rr):
                    ui.rect(rr, T.hover, 4)
                ui.p.setPen(T.success)
                ui.p.setBrush(T.success)
                ui.p.drawEllipse(QPointF(x0 + 6, y + 15), 3.5, 3.5)
                ui.text(QRectF(x0 + 18, y, 70, 30), f":{p['port']}", font(9, W.DemiBold))
                ui.text(QRectF(x0 + 80, y, 220, 30), f"{p['name']} · PID {p['pid']}", font(8), T.text2)
                confirm = self.confirm_kill == p["pid"]
                ui.button(QRectF(x1 - 174, y + 3, 84, 24), "Ouvrir", lambda p=p: self.isl.open_url(f"http://localhost:{p['port']}"),
                          G["globe"])
                ui.button(QRectF(x1 - 84, y + 3, 84, 24), "Confirmer" if confirm else "Arrêter",
                          lambda p=p: self._kill(p["pid"]), G["stop"], danger=True, accent=confirm)
                y += 32
            y += 8
            ui.text(QRectF(x0, y, 300, 18), "Services de développement", font(8.5, W.DemiBold))
            y += 22
            if not dev.services:
                ui.text(QRectF(x0, y, x1 - x0, 18), "Aucun service (PostgreSQL, MySQL, Redis, Docker…) détecté", font(8), T.text3)
                y += 22
            for s in dev.services:
                running = s["status"] == "running"
                pending = "pending" in s["status"]
                col = T.success if running else (T.caution if pending else T.text3)
                ui.p.setPen(col)
                ui.p.setBrush(col)
                ui.p.drawEllipse(QPointF(x0 + 6, y + 15), 3.5, 3.5)
                ui.text(QRectF(x0 + 18, y, x1 - x0 - 140, 30), s["display"], font(8.5))
                ui.button(QRectF(x1 - 96, y + 3, 96, 24), "Arrêter" if running else "Démarrer",
                          lambda s=s: dev.service_toggle(s), G["stop"] if running else G["play"], enabled=not pending)
                y += 32
            ui.text(QRectF(x0, y + 4, x1 - x0, 16), "Démarrer / arrêter un service demande les droits administrateur.",
                    font(7.5), T.text3)
            return y - y0 + 26
        ui.scroll("dev_servers", body, draw)

    def _kill(self, pid):
        if self.confirm_kill == pid:
            self.confirm_kill = None
            self.isl.dev.kill(pid)
        else:
            self.confirm_kill = pid

    # ------------------------------------------------------------------ projets
    def _projects(self, ui, body):
        dev = self.isl.dev
        favs = dev.favorites
        recent = dev.recent
        fav_items = [{"name": os.path.basename(p.rstrip("\\")), "path": p,
                      "ide": next((r["ide"] for r in recent if os.path.normcase(r["path"]) == os.path.normcase(p)), "VS Code")}
                     for p in favs]
        others = [r for r in recent if r["path"] not in favs][:25]

        def row(y, it, fav):
            x0, x1 = body.left() + 8, body.right() - 14
            rr = QRectF(x0 - 4, y, x1 - x0 + 8, 36)
            if ui.visible(rr):
                hov = ui.row_hover(rr)
                if hov:
                    ui.rect(rr, T.hover, 4)
                ui.icon_button(QPointF(x0 + 12, y + 18), G["star_on"] if fav else G["star"],
                               lambda p=it["path"]: dev.toggle_favorite(p), 11, T.caution if fav else T.text3, 26)
                ui.text(QRectF(x0 + 30, y + 2, x1 - x0 - 200, 18), it["name"], font(9, W.DemiBold))
                ui.text(QRectF(x0 + 30, y + 18, x1 - x0 - 200, 16), f"{it['ide']} · {it['path']}", font(7.5), T.text3)
                bx = x1 - 4
                for g_, fn in ((G["terminal"], lambda p=it["path"]: dev.open_terminal(p)),
                               (G["open"], lambda p=it["path"], i=it["ide"]: dev.open_project(p, i)),
                               (G["code"], lambda p=it["path"], i=it["ide"]: dev.select_project(p, i))):
                    ui.icon_button(QPointF(bx - 14, y + 18), g_, fn, 12, size=28)
                    bx -= 30
                ui.row_hit(QRectF(rr.left() + 26, rr.top(), rr.width() - 126, rr.height()),
                           lambda p=it["path"], i=it["ide"]: dev.open_project(p, i))
            return y + 38

        def draw(y0):
            x0 = body.left() + 8
            y = y0
            ui.text(QRectF(x0, y, 300, 18), "Favoris", font(8.5, W.DemiBold))
            y += 22
            if not fav_items:
                ui.text(QRectF(x0, y, 400, 18), "Cliquez sur l'étoile pour épingler un projet", font(8), T.text3)
                y += 24
            for it in fav_items:
                y = row(y, it, True)
            y += 8
            ui.text(QRectF(x0, y, 300, 18), "Récents (VS Code, JetBrains)", font(8.5, W.DemiBold))
            y += 22
            for it in others:
                y = row(y, it, False)
            return y - y0
        ui.scroll("dev_projects", body, draw)
