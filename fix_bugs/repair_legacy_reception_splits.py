"""Run the legacy reception split repair tool from the project root fix_bugs folder."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.repair_legacy_reception_splits import main


if __name__ == "__main__":
    raise SystemExit(main())
