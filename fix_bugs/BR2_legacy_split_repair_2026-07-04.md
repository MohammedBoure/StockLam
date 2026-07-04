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
