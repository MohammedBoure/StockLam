# Billing / Sous-Traitants Module (`ui/widgets/billing/`)

This package manages external transactions with trading partners and subcontractors (Sous-Traitants), providing dedicated interfaces for delivery notes (Bons de Livraison) and return notes (Bons de Retour).

## Files and Purpose

- **`billing_tab.py`**: Main container widget (`BillingTab`) managing the stacked view between the list view (`InvoicesListWidget`) and the transaction editor (`InvoiceEditorWidget`).
- **`invoices_list.py`**: Tabbed interface (`InvoicesListWidget`) separating **Bons de Livraison** and **Bons de Retour** into dedicated tabs with specialized toolbars, search filters, context menus, deletion with stock restoration, and professional PDF export.
- **`invoice_editor.py`**: Comprehensive editor (`InvoiceEditorWidget`) for creating and modifying delivery notes (BL) and return notes (Bon de Retour) with partner selection, barcode scanning, batch allocation, and sales price calculation.
