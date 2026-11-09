"""Lanceur : applications (menu Démarrer + Microsoft Store), favoris, raccourcis personnalisés
(sites, dossiers, fichiers, arguments, PowerShell, Python), groupes, applis récentes."""
import codecs
import glob
import os
import re
import shlex
import shutil
import struct
import subprocess
import threading
import time
import uuid
import webbrowser
import winreg

from PySide6.QtCore import QObject, Signal

from store import settings

NOWIN = 0x08000000
NEW_CONSOLE = 0x00000010
START_DIRS = [r"%ProgramData%\Microsoft\Windows\Start Menu\Programs",
              r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"]
SKIP = re.compile(r"(uninstall|désinstall|desinstall|readme|lisez|help|aide|license|licence|documentation|"
                  r"release notes|website|site web|support|manual|manuel)", re.I)
KNOWN_GUIDS = {
    "{6D809377-6AF0-444B-8957-A3773F02200E}": os.environ.get("ProgramW6432", r"C:\Program Files"),
    "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}": os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}": os.path.expandvars(r"%SystemRoot%\System32"),
    "{F38BF404-1D43-42F2-9305-67DE0B28FC23}": os.path.expandvars(r"%SystemRoot%"),
    "{0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8}": os.path.expandvars(START_DIRS[0]),
    "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}": os.path.expandvars(START_DIRS[1]),
    "{9E3995AB-1F9C-4F13-B827-48B24B6C7174}": os.path.expandvars(r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned"),
}


def _kind_for(target):
    t = target.strip()
    low = t.lower()
    if low.startswith(("http://", "https://", "www.")):
        return "url"
    if low.startswith(("ps:", ">")):
        return "ps"
    if low.startswith("py:") or low.endswith(".py"):
        return "py"
    if low.startswith("shell:appsfolder"):
        return "uwp"
    path = t.strip('"')
    if os.path.isdir(path):
        return "folder"
    if os.path.isfile(path) and not low.endswith((".exe", ".lnk", ".bat", ".cmd", ".appref-ms")):
        return "file"
    return "app"


class Launcher(QObject):
    changed = Signal()
    output = Signal(str, str)  # titre, sortie (commande PowerShell)

    def __init__(self):
        super().__init__()
        self.apps = []        # [{name, target, kind, args}]
        self.recent_apps = []
        self.last_output = None
        threading.Thread(target=self._scan, daemon=True).start()

    # ---------------------------------------------------------------- inventaire
    def _scan(self):
        apps, seen = [], set()
        for d in START_DIRS:
            for lnk in glob.glob(os.path.join(os.path.expandvars(d), "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(lnk))[0]
                if SKIP.search(name) or name.lower() in seen:
                    continue
                seen.add(name.lower())
                apps.append({"name": name, "target": lnk, "kind": "app", "args": ""})
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-StartApps | ForEach-Object { $_.Name + '|' + $_.AppID }"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25,
                               creationflags=NOWIN)
            for line in r.stdout.splitlines():
                if "|" not in line:
                    continue
                name, appid = line.rsplit("|", 1)
                if "!" in appid and name.lower() not in seen and not SKIP.search(name):
                    seen.add(name.lower())
                    apps.append({"name": name, "target": "shell:AppsFolder\\" + appid, "kind": "uwp", "args": ""})
        except Exception:
            pass
        apps.sort(key=lambda a: a["name"].lower())
        self.apps = apps
        self.recent_apps = self._userassist()
        self.changed.emit()

    def _userassist(self):
        """Applications récemment lancées dans Windows (clé UserAssist, noms en ROT13)."""
        out = []
        base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as k:
                guids = [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]
        except OSError:
            return out
        by_name = {a["name"].lower(): a for a in self.apps}
        by_target = {os.path.normcase(a["target"]): a for a in self.apps}
        for g in guids:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + "\\" + g + "\\Count") as k:
                    for i in range(winreg.QueryInfoKey(k)[1]):
                        name, data, _ = winreg.EnumValue(k, i)
                        if not isinstance(data, bytes) or len(data) < 68:
                            continue
                        path = codecs.decode(name, "rot_13")
                        ft = struct.unpack_from("<Q", data, 60)[0]
                        if not ft:
                            continue
                        ts = ft / 1e7 - 11644473600
                        for gid, real in KNOWN_GUIDS.items():
                            if path.upper().startswith(gid):
                                path = real + path[len(gid):]
                        item = None
                        if "!" in path and "\\" not in path:
                            uwp = next((a for a in self.apps if a["target"].lower().endswith(path.lower())), None)
                            nm = uwp["name"] if uwp else path.split("!")[0].split("_")[0].split(".")[-1]
                            item = {"name": nm, "target": "shell:AppsFolder\\" + path, "kind": "uwp", "args": ""}
                        elif path.lower().endswith((".exe", ".lnk")) and os.path.exists(path):
                            a = by_target.get(os.path.normcase(path))
                            stem = os.path.splitext(os.path.basename(path))[0]
                            a = a or by_name.get(stem.lower()) or by_name.get(self._describe(path).lower())
                            item = dict(a) if a else {"name": self._describe(path) or stem, "target": path,
                                                      "kind": "app", "args": ""}
                        if item and not SKIP.search(item["name"]) and item["name"].lower() not in ("explorer",)                                 and not item["name"].endswith(".Root"):
                            item["name"] = item["name"].replace(chr(160), " ")
                            item["ts"] = ts
                            out.append(item)
            except OSError:
                continue
        out.sort(key=lambda a: -a["ts"])
        res, seen = [], set()
        for a in out:
            if a["name"].lower() not in seen:
                seen.add(a["name"].lower())
                res.append(a)
        return res[:12]

    @staticmethod
    def _describe(path):
        """Nom lisible d'un .exe (description du fichier)."""
        try:
            import win32api
            lang, cp = win32api.GetFileVersionInfo(path, r"\VarFileInfo\Translation")[0]
            d = win32api.GetFileVersionInfo(path, rf"\StringFileInfo\{lang:04x}{cp:04x}\FileDescription")
            return (d or "").strip()
        except Exception:
            return ""

    # ---------------------------------------------------------------- favoris / raccourcis / groupes
    @property
    def items(self):
        return settings.get("launcher_items", [])

    @property
    def groups(self):
        return settings.get("launcher_groups", [])

    def add_item(self, name, target, args="", kind=None):
        if target.lower().startswith("www."):
            target = "https://" + target
        it = {"id": uuid.uuid4().hex[:8], "name": name, "target": target, "args": args, "kind": kind or _kind_for(target)}
        settings.set("launcher_items", self.items + [it])
        self.changed.emit()
        return it

    def add_app_favorite(self, app):
        if any(i["target"] == app["target"] for i in self.items):
            return
        self.add_item(app["name"], app["target"], app.get("args", ""), app["kind"])

    def remove_item(self, it):
        settings.set("launcher_items", [i for i in self.items if i["id"] != it["id"]])
        settings.set("launcher_groups", [dict(g, items=[x for x in g["items"] if x != it["id"]]) for g in self.groups])
        self.changed.emit()

    def parse_add(self, text):
        """« Nom = cible arguments », « Groupe Travail : Code, Edge », ou simplement une cible."""
        t = text.strip().lstrip("+").strip()
        m = re.match(r"(?i)groupe\s+(.+?)\s*:\s*(.+)$", t)
        if m:
            return self.add_group(m.group(1), [x.strip() for x in m.group(2).split(",") if x.strip()])
        if "=" in t:
            name, rest = (x.strip() for x in t.split("=", 1))
        else:
            name, rest = None, t
        if not rest:
            return None
        low = rest.lower()
        if low.startswith(("ps:", ">", "py:", "http", "www.")):
            target, args = rest, ""
        else:
            try:
                parts = shlex.split(rest, posix=False)
            except ValueError:
                parts = rest.split()
            # cible avec espaces non guillemetée : on prend le plus long préfixe qui existe
            target, args = parts[0], " ".join(parts[1:])
            for i in range(len(parts), 0, -1):
                cand = " ".join(parts[:i]).strip('"')
                if os.path.exists(cand) or shutil.which(cand):
                    target, args = cand, " ".join(parts[i:])
                    break
            app = self.find_app(target)
            if app and not os.path.exists(target.strip('"')):
                return self.add_item(name or app["name"], app["target"], args, app["kind"])
        name = name or os.path.basename(target.strip('"').rstrip("\\/")) or target
        return self.add_item(name, target.strip('"'), args)

    def add_group(self, name, members):
        ids = []
        for mname in members:
            it = next((i for i in self.items if i["name"].lower() == mname.lower()), None)
            if it is None:
                app = self.find_app(mname)
                if app:
                    it = next((i for i in self.items if i["target"] == app["target"]), None) or \
                        self.add_item(app["name"], app["target"], "", app["kind"])
            if it:
                ids.append(it["id"])
        if not ids:
            return None
        g = {"id": uuid.uuid4().hex[:8], "name": name, "items": ids}
        settings.set("launcher_groups", [x for x in self.groups if x["name"].lower() != name.lower()] + [g])
        self.changed.emit()
        return g

    def remove_group(self, g):
        settings.set("launcher_groups", [x for x in self.groups if x["id"] != g["id"]])
        self.changed.emit()

    def run_group(self, g):
        by = {i["id"]: i for i in self.items}
        for i in g["items"]:
            if i in by:
                self.launch(by[i])
                time.sleep(0.15)

    # ---------------------------------------------------------------- recherche
    def find_app(self, name):
        low = name.lower()
        exact = next((a for a in self.apps if a["name"].lower() == low), None)
        return exact or next((a for a in self.apps if a["name"].lower().startswith(low)), None) or \
            next((a for a in self.apps if low in a["name"].lower()), None)

    def search(self, q, n=12):
        q = q.strip().lower()
        if not q:
            return []
        scored = []
        for a in self.items + self.apps:
            nm = a["name"].lower()
            if nm.startswith(q):
                s = 0
            elif any(w.startswith(q) for w in re.split(r"[\s\-_.]+", nm)):
                s = 1
            elif q in nm:
                s = 2
            elif len(q) > 2 and re.search(".*".join(map(re.escape, q)), nm) and nm[0] == q[0]:
                s = 3
            else:
                continue
            scored.append((s, len(nm), a))
        if any(x[0] <= 2 for x in scored):  # la recherche approximative seulement à défaut de mieux
            scored = [x for x in scored if x[0] <= 2]
        scored.sort(key=lambda x: (x[0], x[1]))
        res, seen = [], set()
        for _, _, a in scored:
            k = a["target"].lower()
            if k not in seen:
                seen.add(k)
                res.append(a)
        return res[:n]

    # ---------------------------------------------------------------- lancement
    def launch(self, it):
        kind, target, args = it.get("kind", "app"), it["target"], it.get("args", "")
        hist = settings.get("launch_hist", {})
        hist[it.get("id") or target] = time.time()
        settings.set("launch_hist", hist)
        try:
            if kind == "url":
                webbrowser.open(target)
            elif kind in ("folder", "file"):
                os.startfile(target)
            elif kind == "uwp":
                subprocess.Popen(["explorer.exe", target])
            elif kind == "ps":
                self.run_powershell(re.sub(r"^(ps:|>)\s*", "", target, flags=re.I) + (" " + args if args else ""))
            elif kind == "py":
                script = re.sub(r"^py:\s*", "", target, flags=re.I).strip('"')
                py = shutil.which("py") or shutil.which("python") or "python"
                subprocess.Popen(f'"{py}" "{script}" {args}', cwd=os.path.dirname(script) or None,
                                 creationflags=NEW_CONSOLE)
            elif args:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None, "open", target, args, None, 1)
            else:
                os.startfile(target)
            return True
        except Exception as e:
            self.output.emit("Impossible de lancer " + it["name"], str(e))
            return False

    def run_powershell(self, cmd):
        def work():
            t = time.time()
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=120, creationflags=NOWIN)
                out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip() or "(aucune sortie)"
                ok = r.returncode == 0
            except subprocess.TimeoutExpired:
                out, ok = "Délai dépassé (120 s)", False
            self.last_output = {"cmd": cmd, "out": out[-4000:], "ok": ok, "time": time.time() - t}
            self.output.emit("PowerShell " + ("terminé" if ok else "en erreur"), cmd)
            self.changed.emit()
        self.last_output = {"cmd": cmd, "out": "Exécution…", "ok": None, "time": 0}
        threading.Thread(target=work, daemon=True).start()
