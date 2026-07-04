r"""One entrypoint for repairing reception/inventory Quantity_Initial consistency.

This file is intentionally kept in fix_bugs so it can be run from the project
root after restoring a database backup or when old transfer-created duplicate
reception rows reappear.

What it does through tools.repair_reception_stock_consistency:
- keeps Inventory_Batches.Quantity_Initial as the Bon de reception quantity;
- repairs Quantity_Initial from the latest ReceptionLogManager SystemLogs entry
  when that entry exists for the same Batch_ID;
- repairs zero Quantity_Initial values from the first positive stock movement;
- keeps Quantity_Current unchanged so actual stock by location is preserved;
- recalculates Reception_Log totals from positive reception quantities;
- writes a SystemLogs entry when --apply is used.

Use dry-run first:
    venv\Scripts\python.exe fix_bugs\fix_legacy_reception_inventory.py --br-id 2

Apply after reviewing planned repairs:
    venv\Scripts\python.exe fix_bugs\fix_legacy_reception_inventory.py --br-id 2 --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.repair_reception_stock_consistency import main


if __name__ == "__main__":
    raise SystemExit(main())
