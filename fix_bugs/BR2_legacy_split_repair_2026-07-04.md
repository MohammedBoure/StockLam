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
