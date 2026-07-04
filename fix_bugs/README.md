Use `fix_legacy_reception_inventory.py` as the single repair entrypoint for legacy Bon de reception and inventory split consistency. Run without `--apply` first, then add `--apply` after reviewing planned repairs.

Legacy reception split repair. Use repair_legacy_reception_splits.py without --apply for dry-run, then add --apply only after reviewing planned repairs. This fixes old transfer-created positive Quantity_Initial split rows and keeps Quantity_Current unchanged.

The repair detector treats same reception/product/internal barcode/lot as one received line even when a legacy transfer split has a different expiry date; expiry values are diagnostic only for this repair path.
