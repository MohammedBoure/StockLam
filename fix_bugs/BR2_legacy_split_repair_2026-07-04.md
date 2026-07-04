# BR2 Legacy Split Repair - 2026-07-04

Repair target:
- `BR_ID`: 2
- `PO_ID`: 252
- Supplier BL ref: 0

What was repaired:
- 26 legacy split rows created by the old location-transfer algorithm.
- Each affected split row had `Quantity_Initial` reset to `0`.
- `Quantity_Current` was kept unchanged, so current stock by location was preserved.

Validation:
- Dry-run before apply found 26 duplicate reception groups.
- Apply completed successfully.
- Dry-run after apply found `rows=0` duplicate groups and `rows=0` planned repairs.

Reception totals after repair:
- `Invoice_Total_HT`: 12,846,553.75
- `Invoice_Total_TVA`: 589,181.47
- `Invoice_Total_TTC`: 12,983,105.77
- `Total_Discount`: 452,629.45

Command used:

```powershell
venv\Scripts\python.exe fix_bugs\repair_legacy_reception_splits.py --br-id 2 --apply
```

Second pass - expiry-mismatched splits:
- The first repair grouped duplicates by expiry date, so rows with corrupted/changed expiry dates could remain visible.
- The repair detector now groups by `BR_ID`, `Product_ID`, `Internal_Barcode`, and `Lot_Number`; expiry dates are reported for diagnostics but are not used to split legacy transfer rows.
- Applied on `2026-07-04` for 2 remaining split rows: `252015` batch `33992` and `252019` batch `33989`.
- Both rows had `Quantity_Initial` reset to `0`; `Quantity_Current` was kept unchanged (`20` and `192`).

Reception totals after second pass:
- `Invoice_Total_HT`: 12,638,953.75
- `Invoice_Total_TVA`: 589,181.47
- `Invoice_Total_TTC`: 12,776,765.77
- `Total_Discount`: 451,369.45

Second-pass validation:
- Full dry-run after apply found `rows=0` duplicate groups and `rows=0` planned repairs.
- `252019`: canonical batch `33549` keeps `Quantity_Initial=216`; split batch `33989` now has `Quantity_Initial=0` and `Quantity_Current=192`.
- `252015`: canonical batch `33545` keeps `Quantity_Initial=70`; split batch `33992` now has `Quantity_Initial=0` and `Quantity_Current=20`.

Restored-database full pass - inventory display fix:
- After the database was restored to the original problematic state, `fix_legacy_reception_inventory.py --br-id 2 --apply` found and repaired 30 legacy split rows again.
- `Quantity_Current` was preserved for all split rows.
- Inventory list display now derives `QTE INIT` from the first positive stock movement when database `Quantity_Initial` is zero due to the reception repair.
- Example validation for `252019` in `STOCK SALLE 00`: displayed `Quantity_Initial=192.00`, stored `Reception_Quantity_Initial=0`, `Quantity_Current=192`.
- Full dry-run after apply found `rows=0` duplicate groups and `rows=0` planned repairs.

Revalidation pass - 252019 semantics:
- The database had returned to an unrepaired state again: dry-run found 30 legacy split rows with positive `Quantity_Initial`.
- Re-applied `fix_legacy_reception_inventory.py --br-id 2 --apply`.
- Post-apply dry-run found `rows=0` duplicate groups and `rows=0` planned repairs.
- Correct meaning after repair: Bon de reception `252019` keeps received quantity `216`; stock row `33989` displays `QTE INIT=192.00` from the first positive movement while stored `Reception_Quantity_Initial=0` prevents Bon duplication.
- `252017` and `252019` remain separate Bon rows even though they share product and lot; navigation from stock uses barcode matching.
Final correction - stock Quantity_Initial is Bon quantity:
- The previous zeroing repair was incorrect for the confirmed business rule.
- The correct rule is that each stock batch `Inventory_Batches.Quantity_Initial` is also the quantity shown in Bon de reception.
- New entrypoint: `fix_bugs\fix_legacy_reception_inventory.py`, backed by `tools\repair_reception_stock_consistency.py`.
- The tool repaired only batches where `Quantity_Initial=0` and a first positive stock movement exists, or where a latest `ReceptionLogManager.update_reception_line` SystemLogs entry proves another initial quantity.
- It does not change `Quantity_Current`.
- It recalculates `Reception_Log` totals after applying repairs.

Applied on restored BR2 data:
- Full dry-run audited 314 batches and planned 13 repairs.
- All 13 repairs were zero `Quantity_Initial` values restored from first positive `Stock_Movement_Log` transfer movements.
- Post-apply dry-run audited 314 batches and planned 0 repairs.

Reception totals after final correction:
- `Invoice_Total_HT`: 15,745,166.64
- `Invoice_Total_TVA`: 709,271.70
- `Invoice_Total_TTC`: 15,912,840.22
- `Total_Discount`: 541,598.12

Key validation:
- `252019` batch `33549`: `Quantity_Initial=216`, `Quantity_Current=0`, location `STOCK SEC`.
- `252019` batch `33989`: `Quantity_Initial=192`, `Quantity_Current=192`, location `STOCK SALLE 00`.
- `252020` batch `33550`: `Quantity_Initial=197`, `Quantity_Current=4`, location `STOCK SEC`.
- `252020` batch `33985`: `Quantity_Initial=12`, `Quantity_Current=165`, location `STOCK SALLE 00`.
- `252021` batch `33551`: `Quantity_Initial=108`, `Quantity_Current=6`, location `STOCK SEC`.
- `252021` batch `33986`: `Quantity_Initial=96`, `Quantity_Current=84`, location `STOCK SALLE 00`.
- `252029` batch `34086`: `Quantity_Initial=2`, restored from first positive movement.
