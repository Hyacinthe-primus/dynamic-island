"""Gardien de la Dynamic Island : la relance si elle se ferme anormalement (plantage, processus tué).
- « Quitter » depuis le menu (code 0) arrête le gardien.
- Après 5 plantages en 1 minute, il abandonne et réaffiche la barre des tâches pour ne jamais
  laisser l'écran sans barre ni île."""
import ctypes
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ISLAND = os.path.join(HERE, "island.py")
SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DynamicIsland", "settings.json")
LOG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DynamicIsland", "watchdog.log")


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def restore_taskbar():
    user32 = ctypes.windll.user32
    for cls in ("Shell_TrayWnd",):
        h = user32.FindWindowW(cls, None)
        if h:
            user32.ShowWindow(h, 5)
    h = 0
    while True:
        h = user32.FindWindowExW(None, h, "Shell_SecondaryTrayWnd", None)
        if not h:
            break
        user32.ShowWindow(h, 5)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            prev = json.load(f).get("taskbar_prev_autohide")
    except Exception:
        prev = None
    if prev is not None:
        class APPBARDATA(ctypes.Structure):
            from ctypes import wintypes as w
            _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uCallbackMessage", w.UINT),
                        ("uEdge", w.UINT), ("rc", w.RECT), ("lParam", w.LPARAM)]
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(abd)
        abd.hWnd = user32.FindWindowW("Shell_TrayWnd", None)
        abd.lParam = 1 if prev else 2
        ctypes.windll.shell32.SHAppBarMessage(0xA, ctypes.byref(abd))


def main():
    ctypes.windll.kernel32.CreateMutexW(None, False, "DynamicIsland_Watchdog")
    if ctypes.windll.kernel32.GetLastError() == 183:
        return  # un gardien tourne déjà
    crashes = []
    while True:
        t = time.time()
        code = subprocess.run([sys.executable, ISLAND], cwd=HERE).returncode
        if code == 0:
            log("arrêt normal")
            break
        log(f"l'île s'est arrêtée (code {code}) après {time.time() - t:.0f} s — relance")
        crashes = [c for c in crashes if time.time() - c < 60] + [time.time()]
        if len(crashes) >= 5:
            log("trop de plantages, abandon")
            break
        time.sleep(2)
    restore_taskbar()


if __name__ == "__main__":
    main()
