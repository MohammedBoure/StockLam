Use `fix_legacy_reception_inventory.py` as the single repair entrypoint for Bon de reception and inventory `Quantity_Initial` consistency.

Correct business rule:
- `Inventory_Batches.Quantity_Initial` is the quantity that must appear in Bon de reception.
- The repair must not zero transfer-created rows.
- If a latest `ReceptionLogManager.update_reception_line` SystemLogs entry exists for a batch, its `line_data.Quantity_Initial` is authoritative.
- If the stored `Quantity_Initial` is zero and the batch has a first positive stock movement, that first positive movement restores the missing initial quantity.
- `Quantity_Current` is never changed by this repair.
- `Reception_Log` totals are recalculated from positive `Inventory_Batches.Quantity_Initial` values.

Run without `--apply` first, then add `--apply` only after reviewing planned repairs:

```powershell
venv\Scripts\python.exe fix_bugs\fix_legacy_reception_inventory.py --br-id 2
venv\Scripts\python.exe fix_bugs\fix_legacy_reception_inventory.py --br-id 2 --apply
```

Use `--barcodes` for targeted validation:

```powershell
venv\Scripts\python.exe fix_bugs\fix_legacy_reception_inventory.py --br-id 2 --barcodes 252019 252020 252021 252029
```
