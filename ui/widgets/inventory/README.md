# Inventory Widgets (`ui/widgets/inventory/`)

This directory contains the widgets, tabs, and dialogs related to inventory and batch management.

## Files and Purpose

- **`inventory_tabs.py`**: Main container widget (`InventoryTab`) hosting the Batches and Dispatch tabs.
- **`dialogs.py`**: Dialogs for batch creation, manual stock adjustments, details inspection, and batch expiration alerts.
- **`location_picker_dialog.py`**: Modal dialog for selecting storage locations hierarchically.
- **`location_tree_combo.py`**: Custom hierarchical tree combo box for storage location selection.
- **`quick_actions.py`**: Quick action buttons and shortcut controls for fast stock operations.
- **`tabs_batches/`**: Modular sub-package managing the detailed batches table, lazy loading, sorting, filtering, and export.
- **`tabs_consumption.py`**: Rapid barcode-driven direct stock consumption tab.
- **`tabs_dispatch.py`**: Stock transfer and dispatch tab between internal locations.
