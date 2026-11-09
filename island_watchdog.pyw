"""Lance le gardien de la Dynamic Island depuis les sources (voir watchdog.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import watchdog  # noqa: E402

watchdog.main()
