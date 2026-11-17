"""Startup stays fast: modules loaded before the first frame must not pull in heavy dependencies."""
import subprocess
import sys
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# imported by the island before its first frame
STARTUP_MODULES = [
    "dynamic_island.core.localization",
    "dynamic_island.engines.agenda",
    "dynamic_island.engines.binance",
    "dynamic_island.engines.devtools",
    "dynamic_island.engines.hotspot",
    "dynamic_island.engines.infos",
    "dynamic_island.engines.media",
    "dynamic_island.engines.network",
    "dynamic_island.engines.nlp",
    "dynamic_island.services.phone",
    "dynamic_island.services.system",
]
# loaded lazily, after the first frame or on first use
HEAVY = ["asyncio", "urllib.request", "http.server", "babel.dates", "babel.numbers", "pycaw.pycaw",
         "winrt.windows.media.control"]


def _loaded_after(code):
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(SRC)!r})
        {code}
        print(",".join(m for m in {HEAVY!r} if m in sys.modules))
    """)
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    return [m for m in out.stdout.strip().split(",") if m]


def test_startup_modules_do_not_import_heavy_dependencies():
    code = "; ".join(f"import {m}" for m in STARTUP_MODULES)
    assert _loaded_after(code) == []


def test_audio_connects_only_on_load():
    assert _loaded_after("from dynamic_island.services.system import Audio; Audio()") == []


def test_nlp_still_parses_day_and_month_names():
    import datetime as dt

    from dynamic_island.engines import nlp

    now = dt.datetime(2026, 11, 17, 9, 0)  # a Tuesday
    assert nlp.parse("Call Paul Friday", now)["date"] == dt.date(2026, 11, 20)
    assert nlp.parse("Dentiste 12 mars", now)["date"] == dt.date(2027, 3, 12)
