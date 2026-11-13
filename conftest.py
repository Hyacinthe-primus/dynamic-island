"""Garantit que le paquet `src/dynamic_island` est prioritaire sur le lanceur racine."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))
