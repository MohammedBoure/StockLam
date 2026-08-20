# Batches Tab Sub-package (`ui/widgets/inventory/tabs_batches/`)

Modular sub-package responsible for displaying and managing inventory batches (lots).

## Files and Purpose

- **`__init__.py`**: Main package entry point and definition of the `BatchesTab` widget class.
- **`_ui.py`**: Builds the filter panels, search bar, table columns configuration, and footer layout.
- **`_table.py`**: Manages table row rendering (`_fill_row`), lazy loading, infinite scroll, and multi-column sorting.
- **`_filters.py`**: Handles local and global filter application (families, suppliers, expiry dates, stock status).
- **`_actions.py`**: Handles batch operations (FEFO validation, direct use, transfer, reclamation notes).
- **`_export.py`**: Exports filtered batch data to Excel, PDF, and prints batch barcode labels.
- **`_combos.py`**: Populates filter combo boxes (families, manufacturers, automates).
- **`_context_menu.py`**: Context menu for right-click actions on batch rows.
- **`_permissions.py`**: Role-based permissions enforcing visibility of financial columns.
- **`_.py`**: Legacy reference implementation.
