"""Stockage local JSON + synchronisation facultative via un dossier cloud
(OneDrive, Google Drive, Dropbox…). Fusion « le plus récent gagne » par élément."""
import json
import os
import time
import uuid

APPDATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DynamicIsland")
SETTINGS_FILE = os.path.join(APPDATA, "settings.json")


class Settings(dict):
    def __init__(self):
        super().__init__()
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                self.update(json.load(f))
        except Exception:
            pass

    def save(self):
        os.makedirs(APPDATA, exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SETTINGS_FILE)

    def set(self, key, value):
        self[key] = value
        self.save()


settings = Settings()


def data_dir():
    sync = settings.get("sync_dir")
    if sync and os.path.isdir(sync):
        return os.path.join(sync, "DynamicIsland")
    return os.path.join(APPDATA, "data")


class Collection:
    """Liste d'éléments {id, mtime, …} enregistrée dans <data_dir>/<name>.json."""

    _all = []

    def __init__(self, name):
        self.name = name
        self.items = []
        self.deleted = set()
        self._mtime = 0
        self.version = 0
        self.load()
        Collection._all.append(self)

    @property
    def path(self):
        return os.path.join(data_dir(), self.name + ".json")

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            self._mtime = os.path.getmtime(self.path)
            return d.get("items", []), set(d.get("deleted", []))
        except Exception:
            return [], set()

    def load(self):
        items, deleted = self._read()
        self.deleted = deleted
        self.items = [i for i in items if i.get("id") not in deleted]
        self.version += 1

    def _merge(self, items, deleted):
        self.deleted |= deleted
        by_id = {i["id"]: i for i in self.items}
        for it in items:
            cur = by_id.get(it["id"])
            if cur is None or it.get("mtime", 0) > cur.get("mtime", 0):
                by_id[it["id"]] = it
        self.items = [i for i in by_id.values() if i["id"] not in self.deleted]
        self.version += 1

    def save(self):
        os.makedirs(data_dir(), exist_ok=True)
        if settings.get("sync_dir"):
            self._merge(*self._read())
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": self.items, "deleted": sorted(self.deleted)[-3000:]}, f, ensure_ascii=False)
        os.replace(tmp, self.path)
        self._mtime = os.path.getmtime(self.path)
        self.version += 1

    def check_sync(self):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            return False
        if m != self._mtime:
            self._merge(*self._read())
            self._mtime = m
            return True
        return False

    # --- opérations
    def add(self, **fields):
        now = time.time()
        it = {"id": uuid.uuid4().hex, "created": now, "mtime": now}
        it.update(fields)
        self.items.append(it)
        self.save()
        return it

    def update(self, item, **fields):
        item.update(fields)
        item["mtime"] = time.time()
        self.save()

    def remove(self, item):
        if item in self.items:
            self.items.remove(item)
        self.deleted.add(item["id"])
        self.save()

    def get(self, id_):
        for i in self.items:
            if i["id"] == id_:
                return i
        return None

    @classmethod
    def sync_all(cls):
        changed = False
        for c in cls._all:
            changed |= c.check_sync()
        return changed

    @classmethod
    def save_all(cls):
        """Après changement du dossier de synchro : fusionne la mémoire avec le nouveau dossier."""
        for c in cls._all:
            c.save()
