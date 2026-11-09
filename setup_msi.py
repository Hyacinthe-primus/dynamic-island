"""Construction de l'application Windows (cx_Freeze).

    python setup_msi.py build_exe   → build/  (application portable : DynamicIsland.exe)
    python setup_msi.py bdist_msi   → dist/   (installateur Windows .msi)

L'installateur s'installe pour l'utilisateur courant (sans droits administrateur) dans
%LOCALAPPDATA%\\Programs\\Dynamic Island, crée les raccourcis menu Démarrer + Bureau et le
démarrage avec Windows ; tout est retiré à la désinstallation (les données de
%APPDATA%\\DynamicIsland sont conservées)."""
import sys

from cx_Freeze import Executable, setup

VERSION = "1.0.0"
UPGRADE_CODE = "{32BDF7EE-F765-4C20-AB17-EBB9CFFF65DA}"  # ne jamais changer : permet les mises à jour

build_exe_options = {
    "packages": [
        "winrt", "comtypes", "pycaw", "screen_brightness_control", "wmi", "icalendar",
        "recurring_ical_events", "qrcode", "cryptography", "tzdata", "psutil", "win32com",
        "pythoncom", "pywintypes", "zoneinfo", "xml", "sqlite3", "asyncio", "ctypes",
    ],
    "includes": [
        "island", "watchdog", "paths", "theme", "ui", "icons", "store", "nlp", "system", "network", "hotspot",
        "media", "agenda", "timers", "tasks", "infos", "binance", "devtools", "launcher", "files", "clipboard",
        "phone", "tab_home", "tab_agenda", "tab_timers", "tab_tasks", "tab_launcher", "tab_files", "tab_phone",
        "tab_infos", "tab_wallet", "tab_dev", "tab_controls", "tab_clip",
    ],
    "excludes": [
        "tkinter", "unittest", "pydoc_data", "test", "distutils", "setuptools", "pip",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebView",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtGraphs", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtQuick",
        "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtDesigner",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtLocation", "PySide6.QtPositioning",
        "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtCanvasPainter",
        "PIL", "cx_Freeze",
    ],
    "include_files": [
        ("phone_page.html", "phone_page.html"),
        ("assets/island.ico", "assets/island.ico"),
        ("README.md", "README.md"),
    ],
    "include_msvcr": True,
    "optimize": 1,
}

bdist_msi_options = {
    "upgrade_code": UPGRADE_CODE,
    "add_to_path": False,
    "all_users": False,                                         # installation par utilisateur, sans UAC
    "initial_target_dir": r"[LocalAppDataFolder]Programs\Dynamic Island",
    "install_icon": "assets/island.ico",
    "product_code": None,
    "output_name": f"DynamicIsland-{VERSION}-win64.msi",
    "summary_data": {
        "author": "arielDirema",
        "comments": "Dynamic Island pour Windows 11",
        "keywords": "dynamic island, windows 11, barre des tâches",
    },
    "data": {
        # Raccourci sur le Bureau (celui du menu Démarrer est créé par l'exécutable ci-dessous)
        "Shortcut": [
            ("DesktopShortcut", "DesktopFolder", "Dynamic Island", "TARGETDIR",
             "[TARGETDIR]DynamicIsland.exe", None, "Dynamic Island pour Windows 11", None, None, None, None,
             "TARGETDIR"),
        ],
        # Démarrage avec Windows (valeur gérée par l'installateur : retirée à la désinstallation)
        "Registry": [
            ("AutoStart", 1, r"Software\Microsoft\Windows\CurrentVersion\Run", "DynamicIsland",
             '"[TARGETDIR]DynamicIsland.exe"', "TARGETDIR"),
        ],
    },
}

setup(
    name="Dynamic Island",
    version=VERSION,
    description="Dynamic Island pour Windows 11",
    author="arielDirema",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=[
        Executable(
            "dynamic_island.py",
            base="gui" if sys.platform == "win32" else None,     # pas de console
            target_name="DynamicIsland.exe",
            icon="assets/island.ico",
            shortcut_name="Dynamic Island",
            shortcut_dir="ProgramMenuFolder",
            copyright="arielDirema",
        )
    ],
)
