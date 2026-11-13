"""Persistent application settings (%APPDATA%\\DynamicIsland\\settings.json)."""
import json
import os

from dynamic_island.core.config.paths import APPDATA, SETTINGS_FILE


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
