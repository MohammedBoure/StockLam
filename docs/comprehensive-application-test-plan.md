# StockLam Comprehensive Application Test Plan

## Purpose

This document defines a complete manual and regression test plan for the StockLam application. It is designed to be used before production use, after database restore/import operations, after major feature changes, and before deploying updates to real laboratory or inventory data.

Each section contains completion checkboxes. Mark a checkbox as `[x]` only when the test has been executed, the expected result has been verified, and any related evidence has been saved.

## Test Completion Rules

- `[ ]` Not tested yet.
- `[x]` Tested and passed.
- `[!]` Tested with issue found. Create a bug report before release.
- `[N/A]` Not applicable for this installation.

For every failed item, record:

- Tester name.
- Date and time.
- Application version or commit hash.
- Database name.
- Screenshot or log file.
- Exact reproduction steps.
- Expected result.
- Actual result.

## Release Sign-Off Checklist

| Done | Area | Owner | Date | Evidence / Notes |
| --- | --- | --- | --- | --- |
| [ ] | Environment prepared |  |  |  |
| [ ] | Database schema verified |  |  |  |
| [ ] | Authentication tested |  |  |  |
| [ ] | Permissions tested |  |  |  |
| [ ] | Dashboard tested |  |  |  |
| [ ] | Master data tested |  |  |  |
| [ ] | Procurement tested |  |  |  |
| [ ] | Stock and inventory tested |  |  |  |
| [ ] | Inventaire tested |  |  |  |
| [ ] | Finance and billing tested |  |  |  |
| [ ] | Services tested |  |  |  |
| [ ] | History and audit tested |  |  |  |
| [ ] | User management tested |  |  |  |
| [ ] | Settings tested |  |  |  |
| [ ] | Backup and restore tested |  |  |  |
| [ ] | Exports tested |  |  |  |
| [ ] | Error handling tested |  |  |  |
| [ ] | Performance tested |  |  |  |
| [ ] | Final regression completed |  |  |  |

## 1. Test Environment

### 1.1 Environment Setup

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Install dependencies inside the project virtual environment. | Application dependencies install without errors. |  |
| [ ] | Start the application from `venv` using `python main.py`. | Application starts without Python path errors. |  |
| [ ] | Verify `.env` database settings. | Host, port, database, and user point to the intended test database. |  |
| [ ] | Verify the application does not use production data during testing. | Test database is clearly separated from production. |  |
| [ ] | Verify logs are written and readable. | Startup, login, database, and application errors appear in logs. |  |
| [ ] | Verify screen resolution support: small laptop, standard desktop, wide screen. | UI remains usable without clipped text or overlapping controls. |  |

### 1.2 Startup Checks

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Run `venv\Scripts\python.exe -m compileall database ui test`. | Compilation succeeds. |  |
| [ ] | Run `venv\Scripts\python.exe -m unittest discover`. | All tests pass. |  |
| [ ] | Start application with valid database connection. | Login/main window opens normally. |  |
| [ ] | Start application with database unavailable. | Application shows a clear connection error and does not crash. |  |
| [ ] | Verify auto-backup worker startup. | Worker starts only when configured and logs status clearly. |  |

## 2. Database and Schema Validation

### 2.1 Required Tables

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify all base application tables exist. | No missing table errors at startup or navigation. |  |
| [ ] | Verify users table exists and contains expected admin/test users. | Login users can be loaded. |  |
| [ ] | Verify master data tables exist. | Products, suppliers, families, locations, automates load. |  |
| [ ] | Verify inventory tables exist. | Inventory batches, stock movement logs, and related tables load. |  |
| [ ] | Verify procurement tables exist. | Receptions, purchases, transfer logs, credit notes load. |  |
| [ ] | Verify billing/finance tables exist. | Finance pages open without schema errors. |  |
| [ ] | Verify Inventaire tables exist. | `Inventory_Count_Sessions`, `Inventory_Count_Lines`, and `Inventory_Count_Scans` exist. |  |

### 2.2 Constraints and Indexes

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify primary keys on all major tables. | Each table has stable unique identifiers. |  |
| [ ] | Verify foreign keys where required. | Related rows cannot become orphaned in normal flows. |  |
| [ ] | Verify barcode uniqueness rules. | Duplicate internal barcode is rejected or handled explicitly. |  |
| [ ] | Verify Inventaire indexes on session, barcode, status, and scan time. | Session loading and scanning remain fast. |  |
| [ ] | Verify stock movement log indexes. | Movement history search remains fast. |  |

### 2.3 Migration and Startup Schema Checks

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Start with schema checks enabled in test environment. | Missing tables/columns are created or reported clearly. |  |
| [ ] | Start with schema checks disabled. | Application does not silently fail if schema is incomplete; errors are clear. |  |
| [ ] | Verify table import order for restore/import. | Parent tables load before child tables. |  |
| [ ] | Restore a test database from backup. | Restore completes or reports actionable errors. |  |

## 3. Authentication

### 3.1 Login

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Login with valid admin credentials. | Admin reaches main window. |  |
| [ ] | Login with invalid password. | Login is rejected with a clear message. |  |
| [ ] | Login with unknown username. | Login is rejected with a clear message. |  |
| [ ] | Login when database is unavailable. | Application shows a database error and does not crash. |  |
| [ ] | Verify password field hides characters. | Password is not visible while typing. |  |
| [ ] | Verify auto-login behavior if configured. | Auto-login works only for intended account. |  |

### 3.2 Session and Logout

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Logout or close application after login. | Session ends cleanly. |  |
| [ ] | Restart application after closing. | No stale UI state breaks startup. |  |
| [ ] | Switch users if supported. | Permissions refresh correctly for the new user. |  |

## 4. Permissions and Navigation

### 4.1 Main Sidebar

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Admin user opens application. | All authorized sidebar buttons appear. |  |
| [ ] | Restricted user opens application. | Only permitted pages appear. |  |
| [ ] | User without any navigation permission logs in. | Application shows a clear message instead of a blank unusable window. |  |
| [ ] | Click Dashboard. | Dashboard opens. |  |
| [ ] | Click Data. | Master data page opens. |  |
| [ ] | Click Procurement. | Procurement page opens. |  |
| [ ] | Click Stock & Magasin. | Inventory page opens. |  |
| [ ] | Click Inventaire. | Inventaire page opens only with `nav_inventaire`. |  |
| [ ] | Click Finance. | Finance page opens only with finance permission. |  |
| [ ] | Click Services. | Services page opens only with service permission. |  |
| [ ] | Click History. | History page opens only with history permission. |  |
| [ ] | Click Users. | User management opens only with user admin permission. |  |
| [ ] | Click Settings. | Settings opens according to existing settings behavior. |  |

### 4.2 Action Permissions

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Remove create permission from a user. | Create buttons are hidden or disabled. |  |
| [ ] | Remove edit permission from a user. | Edit actions are hidden or disabled. |  |
| [ ] | Remove delete/cancel permission from a user. | Delete/cancel actions are hidden or disabled. |  |
| [ ] | Remove export permission from a user. | Export actions are hidden or disabled. |  |
| [ ] | Verify direct page switching cannot bypass permissions. | Unauthorized page is blocked. |  |
| [ ] | Verify permissions saved in list, dict, and JSON formats if supported. | Permission reader handles all supported formats. |  |

## 5. Dashboard

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open dashboard with normal data. | Cards and charts load without errors. |  |
| [ ] | Open dashboard with empty database. | UI displays empty state gracefully. |  |
| [ ] | Verify stock alerts. | Low stock and expiry alerts match database values. |  |
| [ ] | Verify financial summaries. | Amounts display with decimals. |  |
| [ ] | Verify quantities display as integers. | Quantities do not show unnecessary decimal places. |  |
| [ ] | Refresh dashboard. | Values update without duplicate widgets or UI freeze. |  |

## 6. Master Data

### 6.1 Products

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create product with valid required fields. | Product is saved and appears in list/search. |  |
| [ ] | Attempt product creation with missing required fields. | Clear validation message appears. |  |
| [ ] | Edit product name, family, barcode, unit, and manufacturer reference. | Changes persist after refresh. |  |
| [ ] | Attempt duplicate product barcode if uniqueness is required. | Duplicate is rejected or handled clearly. |  |
| [ ] | Search by product name. | Matching products appear. |  |
| [ ] | Search by barcode. | Matching product appears. |  |
| [ ] | Search by manufacturer reference. | Matching product appears. |  |
| [ ] | Disable/archive product if supported. | Product no longer appears in active workflows unless expected. |  |

### 6.2 Families, Suppliers, Manufacturers, Automates, Locations

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create family. | Family appears in selectors. |  |
| [ ] | Edit family. | Changes persist. |  |
| [ ] | Create supplier. | Supplier appears in procurement workflows. |  |
| [ ] | Edit supplier contact and payment information. | Changes persist. |  |
| [ ] | Create manufacturer if supported. | Manufacturer appears for products. |  |
| [ ] | Create automate. | Automate appears in product/test workflows. |  |
| [ ] | Create location. | Location appears in inventory and Inventaire scope selectors. |  |
| [ ] | Attempt deleting data used by existing products or batches. | Application prevents unsafe deletion or explains dependency. |  |

## 7. Procurement

### 7.1 Purchase and Reception

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create a procurement/reception document with one product. | Document is saved. |  |
| [ ] | Create reception with multiple products/lots. | All lines are saved correctly. |  |
| [ ] | Verify received quantities create inventory batches. | `Inventory_Batches` quantity matches reception. |  |
| [ ] | Verify internal barcode generation. | Generated barcodes are unique and readable. |  |
| [ ] | Verify lot number and expiry date. | Batch stores correct lot and expiry. |  |
| [ ] | Verify unit price and financial values. | Amounts display with decimals and totals are correct. |  |
| [ ] | Save reception with missing required fields. | Clear validation message appears. |  |
| [ ] | Cancel reception if supported. | Stock and logs remain consistent. |  |

### 7.2 External Transfers and Credit Notes

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create external transfer. | Transfer is saved with all details. |  |
| [ ] | Verify transferred quantities affect stock correctly. | Batch quantity decreases as expected. |  |
| [ ] | Create credit note. | Credit note is saved and linked to related data. |  |
| [ ] | Verify credit note totals. | Amounts and taxes are correct. |  |
| [ ] | Try transfer with insufficient stock. | Application blocks or clearly reports the issue. |  |

## 8. Stock and Magasin

### 8.1 Inventory Batches

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open Stock & Magasin page. | Page loads without errors. |  |
| [ ] | Load inventory batches. | Existing batches appear. |  |
| [ ] | Filter by product. | Matching batches appear. |  |
| [ ] | Filter by location. | Matching batches appear. |  |
| [ ] | Filter by status. | Available, depleted, expired, and quarantined filters work. |  |
| [ ] | Verify quantities display as integers. | No unnecessary decimal places for quantities. |  |
| [ ] | Verify prices display with decimals. | Monetary values keep decimals. |  |
| [ ] | Open batch details. | Product, lot, barcode, quantity, status, and location are correct. |  |
| [ ] | Adjust stock if supported outside Inventaire. | Quantity and movement log are updated correctly. |  |
| [ ] | Set batch to quarantined if supported. | Batch cannot be consumed by normal workflows. |  |
| [ ] | Set batch to depleted if quantity becomes zero. | Status changes to depleted. |  |

### 8.2 Stock Movement Log

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify reception creates stock movement log. | Movement type and quantity are correct. |  |
| [ ] | Verify transfer/dispatch creates stock movement log. | Negative quantity movement is correct. |  |
| [ ] | Verify adjustment creates stock movement log. | Adjustment value is correct. |  |
| [ ] | Filter stock movement history by product. | Correct movements appear. |  |
| [ ] | Filter stock movement history by date. | Correct date range appears. |  |
| [ ] | Verify movement user ID. | Movement is linked to the acting user. |  |

### 8.3 Containers and Dispatch

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create or load active containers if supported. | Container list loads correctly. |  |
| [ ] | Dispatch stock to a container/service if supported. | Batch quantity decreases correctly. |  |
| [ ] | Dispatch with insufficient stock. | Operation is blocked safely. |  |
| [ ] | Verify dispatch history. | Dispatch appears in history and movement logs. |  |

## 9. Inventaire

### 9.1 Navigation and Permissions

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | User with `nav_inventaire` sees Inventaire in sidebar. | Sidebar button appears. |  |
| [ ] | User without `nav_inventaire` does not see Inventaire. | Sidebar button hidden or disabled. |  |
| [ ] | User without create permission opens Inventaire. | New session button hidden or disabled. |  |
| [ ] | User without scan permission opens Inventaire. | Scanner button hidden or disabled. |  |
| [ ] | User without apply permission opens Inventaire. | Apply button hidden or disabled. |  |
| [ ] | User without cancel permission opens Inventaire. | Cancel button hidden or disabled. |  |
| [ ] | User without export permission opens Inventaire. | Export button hidden or disabled. |  |

### 9.2 Session Creation and Scope

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Create ALL scope session. | Snapshot includes all positive-quantity batches. |  |
| [ ] | Create LOCATION scope session. | User can search/select real location; snapshot includes only that location. |  |
| [ ] | Create FAMILY scope session. | User can search/select real family; snapshot includes only that family. |  |
| [ ] | Create PRODUCT scope session. | User can search/select real product; snapshot includes only that product. |  |
| [ ] | Try scope requiring ID without selecting ID. | Validation blocks creation. |  |
| [ ] | Create session with notes. | Notes are saved. |  |
| [ ] | Verify session status after creation. | Status becomes `Counting`. |  |

### 9.3 Snapshot Accuracy

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify each snapshot line has Batch_ID. | Existing batches are linked. |  |
| [ ] | Verify snapshot Program_Qty equals current batch quantity at creation time. | Values match. |  |
| [ ] | Verify Counted_Qty starts at zero. | Counted quantity is `0`. |  |
| [ ] | Verify Difference_Qty starts as negative program quantity. | Difference is `0 - Program_Qty`. |  |
| [ ] | Verify Line_Status starts as `NOT_COUNTED`. | Status is correct. |  |
| [ ] | Verify zero-quantity batches are excluded. | Depleted/zero batches are not counted unless expected. |  |

### 9.4 Scanner Workflow

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open scanner for Counting session. | Full-screen scanner dialog opens. |  |
| [ ] | Scan known internal barcode. | Product details load and quantity input is selected. |  |
| [ ] | Scan known product barcode. | Correct product line is found. |  |
| [ ] | Scan known manufacturer reference. | Correct product line is found. |  |
| [ ] | Scan barcode with spaces or hyphens. | Matching product is still found when equivalent. |  |
| [ ] | Enter physical quantity and press Enter. | Count is recorded and scanner returns to barcode input. |  |
| [ ] | Scan unknown barcode. | Unknown status appears and unknown scan is recorded. |  |
| [ ] | Scan multiple products continuously. | Scanner remains responsive and focus returns correctly. |  |
| [ ] | Verify last 20 scans table. | Only latest 20 records are shown in dialog. |  |
| [ ] | Verify main Inventaire page refresh after scan. | Summary and lines update. |  |

### 9.5 Manual Count Corrections

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Manually correct counted quantity for a line. | Difference and status recalculate. |  |
| [ ] | Set counted quantity equal to snapshot. | Status becomes `OK`. |  |
| [ ] | Set counted quantity lower than snapshot. | Status becomes `SHORT`. |  |
| [ ] | Set counted quantity higher than snapshot. | Status becomes `EXCESS`. |  |
| [ ] | Try negative counted quantity. | Operation is rejected. |  |

### 9.6 Review, Cancel, and Apply

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Mark Counting session as Review. | Status becomes `Review`. |  |
| [ ] | Cancel Counting session. | Status becomes `Cancelled`. |  |
| [ ] | Attempt to cancel Applied session. | Operation is rejected. |  |
| [ ] | Apply session without conflicts. | Quantities update and session becomes `Applied`. |  |
| [ ] | Apply session twice. | Second apply is rejected. |  |
| [ ] | Apply session with UNKNOWN lines without confirmation/allow flag. | Operation is rejected. |  |
| [ ] | Apply session with UNKNOWN lines and allow flag. | Known lines apply according to business rules. |  |
| [ ] | Change stock after snapshot before apply. | Conflict is detected and no batch is modified. |  |
| [ ] | Verify shortage adjustment. | Negative `Qty_Change` is logged. |  |
| [ ] | Verify excess adjustment. | Positive `Qty_Change` is logged. |  |
| [ ] | Verify counted zero. | Batch quantity becomes zero and status becomes `Depleted`. |  |
| [ ] | Verify depleted batch counted above zero. | Status becomes `Available` if previously depleted. |  |
| [ ] | Verify quarantined/expired batch status. | Status is not overwritten by apply. |  |

### 9.7 Inventaire Export

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Export session to `.xlsx`. | Excel file is created. |  |
| [ ] | Open exported file. | File opens in Excel or compatible viewer. |  |
| [ ] | Verify `Résumé` sheet. | Session and summary data are correct. |  |
| [ ] | Verify `Lignes` sheet. | Product, barcode, lot, location, quantities, difference, and status are correct. |  |
| [ ] | Verify `Scans` sheet with scans. | Scan rows are exported. |  |
| [ ] | Export session without scans. | File still exports correctly. |  |

## 10. Finance and Billing

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open Finance page. | Page loads without permission or schema errors. |  |
| [ ] | Create invoice/billing item if supported. | Document is saved. |  |
| [ ] | Verify monetary formatting. | Amounts display with decimals. |  |
| [ ] | Verify totals, discounts, taxes, and balances. | Calculations are correct. |  |
| [ ] | Record payment/versement if supported. | Payment appears and balance updates. |  |
| [ ] | Export or print financial document if supported. | Output is generated correctly. |  |
| [ ] | Verify restricted user cannot see financial details. | Financial data is hidden according to permissions. |  |

## 11. Services

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open Services page. | Page loads normally. |  |
| [ ] | Create service record if supported. | Service is saved. |  |
| [ ] | Edit service record. | Changes persist. |  |
| [ ] | Link service to stock usage if supported. | Stock decreases and movement log is created. |  |
| [ ] | Search/filter services. | Results match filter criteria. |  |
| [ ] | Verify unauthorized user cannot access services. | Page or actions are blocked. |  |

## 12. History and Audit

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open History page. | Page loads without errors. |  |
| [ ] | Search by date range. | Correct records appear. |  |
| [ ] | Search by user. | Correct records appear. |  |
| [ ] | Search by movement/action type. | Correct records appear. |  |
| [ ] | Verify stock adjustment audit. | Inventaire adjustments are visible. |  |
| [ ] | Verify login or user actions if logged. | Events are visible. |  |
| [ ] | Export history if supported. | Export file is correct. |  |

## 13. User Management

### 13.1 Users

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open Users page as admin. | User management loads. |  |
| [ ] | Open Users page as non-admin. | Access is blocked. |  |
| [ ] | Create user with valid username/password. | User is saved. |  |
| [ ] | Attempt duplicate username. | Duplicate is rejected. |  |
| [ ] | Edit user display name or role. | Changes persist. |  |
| [ ] | Disable user if supported. | Disabled user cannot login. |  |
| [ ] | Reset/change password. | New password works and old password fails. |  |

### 13.2 Permission Management

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Grant navigation permission. | Sidebar page appears for user. |  |
| [ ] | Remove navigation permission. | Sidebar page disappears for user. |  |
| [ ] | Grant Inventaire action permissions. | Corresponding buttons appear. |  |
| [ ] | Remove Inventaire action permissions. | Corresponding buttons hide or disable. |  |
| [ ] | Save permissions and restart app. | Permissions persist. |  |
| [ ] | Verify invalid permission data does not crash app. | App handles it safely. |  |

## 14. Settings

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Open Settings page. | Settings load normally. |  |
| [ ] | Change application setting. | Setting saves and applies correctly. |  |
| [ ] | Change database-related setting in test environment only. | Application reconnects or asks for restart safely. |  |
| [ ] | Verify settings validation. | Invalid values are rejected. |  |
| [ ] | Verify settings persistence after restart. | Values remain saved. |  |
| [ ] | Verify restricted user cannot change protected settings. | Controls are hidden or disabled. |  |

## 15. Backup and Restore

### 15.1 Backup

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Run manual backup. | Backup file is created. |  |
| [ ] | Verify auto-backup creates file. | File appears at configured interval/path. |  |
| [ ] | Verify backup contains expected tables/files. | Archive content is complete. |  |
| [ ] | Verify backup file naming. | Name includes date/time and is unique. |  |
| [ ] | Verify backup failure handling. | Clear error appears and app does not crash. |  |

### 15.2 Restore

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Restore unencrypted backup. | Restore completes successfully. |  |
| [ ] | Restore encrypted backup without password. | Clear password-required error appears. |  |
| [ ] | Restore encrypted backup with password if supported. | Restore completes successfully. |  |
| [ ] | Restore backup containing duplicate barcode. | Restore reports duplicate clearly and leaves database consistent. |  |
| [ ] | Verify restore rollback on failure. | Partial restore does not corrupt database. |  |
| [ ] | Verify restored login. | Users can login after restore. |  |
| [ ] | Verify restored stock quantities. | Quantities match backup source. |  |

## 16. Export and Reporting

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Export product list. | File contains correct products. |  |
| [ ] | Export inventory batches. | File contains correct batch data. |  |
| [ ] | Export stock movement log. | File contains correct movement data. |  |
| [ ] | Export Inventaire session. | File contains summary, lines, and scans. |  |
| [ ] | Export finance report. | Amounts are correct. |  |
| [ ] | Cancel file dialog. | No export occurs and no error appears. |  |
| [ ] | Export to path without extension. | Application adds expected extension if supported. |  |
| [ ] | Export to invalid/unwritable path. | Clear error appears. |  |

## 17. Data Formatting and Localization

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify all quantities in main workflows. | Quantities display as integers. |  |
| [ ] | Verify money amounts. | Amounts display with decimal separators. |  |
| [ ] | Verify dates. | Dates are readable and consistent. |  |
| [ ] | Verify French UI labels. | Labels are consistent and understandable. |  |
| [ ] | Verify Arabic/French user-entered text. | Text saves and displays without encoding issues. |  |
| [ ] | Verify long product names. | Text does not overlap or break table layout. |  |

## 18. Error Handling

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Disconnect database during normal browsing. | Error is clear and app remains controlled. |  |
| [ ] | Trigger duplicate key error. | User sees understandable message. |  |
| [ ] | Trigger validation error. | User sees field-specific or clear message. |  |
| [ ] | Trigger export failure. | Error is shown and no crash occurs. |  |
| [ ] | Trigger restore failure. | Error is shown and database remains consistent. |  |
| [ ] | Review logs after errors. | Logs contain actionable technical details. |  |

## 19. Performance and Large Data

### 19.1 Baseline Data Volumes

Use test data volumes close to real expected usage:

- 1,000 products.
- 10,000 inventory batches.
- 100,000 stock movement log rows.
- 20 Inventaire sessions.
- 200,000 Inventaire lines.
- 200,000 Inventaire scans.

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Start application with large database. | Startup remains acceptable. |  |
| [ ] | Open Stock & Magasin with large batch table. | Page loads without freezing. |  |
| [ ] | Search product by name/barcode. | Results appear quickly. |  |
| [ ] | Open Inventaire with many sessions. | Sessions load quickly or are limited. |  |
| [ ] | Open large Inventaire session. | Lines load without UI freeze or use pagination/lazy loading. |  |
| [ ] | Scan barcodes continuously for 5 minutes. | Scanner remains responsive. |  |
| [ ] | Apply large Inventaire session. | Transaction completes or reports conflicts safely. |  |
| [ ] | Export large Inventaire session. | Export completes within acceptable time. |  |

### 19.2 Long-Term Usage

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Simulate inventory count every 2 months for 3 years. | Historical sessions remain accessible. |  |
| [ ] | Verify old sessions do not slow current scanning. | Current session scanning remains fast. |  |
| [ ] | Verify backup size growth. | Backup remains manageable. |  |
| [ ] | Verify restore time with multi-year data. | Restore completes within acceptable time. |  |

## 20. Security and Data Safety

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Verify database credentials are not displayed in UI. | Sensitive values are hidden. |  |
| [ ] | Verify passwords are not logged. | Logs do not contain passwords. |  |
| [ ] | Verify SQL inputs use parameterized queries for critical flows. | No SQL injection risk in tested flows. |  |
| [ ] | Try SQL-like text in search fields. | Application treats it as text and does not crash. |  |
| [ ] | Verify restricted finance data access. | Unauthorized users cannot view financial data. |  |
| [ ] | Verify restricted settings access. | Unauthorized users cannot change settings. |  |
| [ ] | Verify backup files are protected according to local policy. | Backup path is not exposed to unauthorized users. |  |

## 21. Regression Suite

Run this suite after every significant code change.

| Done | Test | Expected Result | Evidence / Notes |
| --- | --- | --- | --- |
| [ ] | Compile all Python modules. | No syntax/import errors. |  |
| [ ] | Run unit tests. | All tests pass. |  |
| [ ] | Login as admin. | Main window opens. |  |
| [ ] | Navigate every sidebar page. | Each page opens without crash. |  |
| [ ] | Create product. | Product saves. |  |
| [ ] | Create reception. | Batch is created. |  |
| [ ] | View inventory batch. | Batch appears correctly. |  |
| [ ] | Create Inventaire session. | Snapshot is created. |  |
| [ ] | Scan known barcode. | Count updates. |  |
| [ ] | Scan unknown barcode. | Unknown scan is recorded. |  |
| [ ] | Apply Inventaire session. | Batch quantities and movement logs update. |  |
| [ ] | Export Inventaire session. | Excel file is valid. |  |
| [ ] | Create backup. | Backup file is valid. |  |
| [ ] | Restore backup in test database. | Restore succeeds and data is correct. |  |

## 22. Final Acceptance Criteria

The release can be accepted only when:

- All critical sections are marked `[x]`.
- No blocker or high-severity bug remains open.
- Database backup and restore have been tested successfully.
- Admin and restricted-user permissions have been validated.
- Stock quantities, monetary amounts, and movement logs are correct.
- Inventaire can create, scan, review, apply, cancel, and export sessions.
- All automated tests pass.
- The final release commit hash is recorded.

| Done | Acceptance Item | Evidence / Notes |
| --- | --- | --- |
| [ ] | No blocker bugs remain. |  |
| [ ] | No high-severity data integrity bugs remain. |  |
| [ ] | Automated tests pass. |  |
| [ ] | Manual smoke test pass. |  |
| [ ] | Backup and restore pass. |  |
| [ ] | Final sign-off completed. |  |

## 23. Final Sign-Off

| Role | Name | Signature / Confirmation | Date |
| --- | --- | --- | --- |
| Tester |  |  |  |
| Stock/Inventory Owner |  |  |  |
| Finance Owner, if applicable |  |  |  |
| Application Owner |  |  |  |

