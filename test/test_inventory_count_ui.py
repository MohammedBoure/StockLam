import os
import unittest
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.inventory.inventory_count_scan_dialog import InventoryCountScanDialog
from ui.widgets.inventory.inventory_count_tab import InventoryCountTab


class FakeInventoryCounts:
    def __init__(self):
        self.sessions = [
            {
                "Session_ID": 101,
                "Session_Name": "Inventaire principal",
                "Status": "Counting",
                "Started_At": "2026-06-07 08:00:00",
                "Created_By": 1,
            },
            {
                "Session_ID": 102,
                "Session_Name": "Session appliquee",
                "Status": "Applied",
                "Started_At": "2026-06-07 09:00:00",
                "Created_By": 1,
            },
        ]
        self.lines = [
            {
                "Line_ID": 1,
                "Product_Name": "Glucose",
                "Internal_Barcode": "INT-001",
                "Product_Barcode": "PROD-001",
                "Manuf_Cat_No": "REF-001",
                "Lot_Number": "LOT-A",
                "Expiry_Date": "2027-01-31",
                "Location_Name": "Stock A",
                "Program_Qty_Snapshot": Decimal("10"),
                "Counted_Qty": Decimal("0"),
                "Difference_Qty": Decimal("-10"),
                "Line_Status": "NOT_COUNTED",
                "Comment": "",
                "Family_Name": "Biochimie",
                "Manuf_Name": "Acme",
                "Automate_Name": "Auto 1",
                "Batch_Status": "Available",
                "Stock_Unit": "Box",
                "Usage_Unit": "Test",
                "Storage_Temp_Req": "2-8C",
                "Quantity_Current": Decimal("10"),
                "Quantity_Initial": Decimal("12"),
                "Reception_Note": "RN-1",
            },
            {
                "Line_ID": 2,
                "Product_Name": "Controle",
                "Internal_Barcode": "INT-002",
                "Product_Barcode": "PROD-002",
                "Manuf_Cat_No": "REF-002",
                "Lot_Number": "LOT-B",
                "Expiry_Date": "2027-02-28",
                "Location_Name": "Stock B",
                "Program_Qty_Snapshot": Decimal("5"),
                "Counted_Qty": Decimal("7"),
                "Difference_Qty": Decimal("2"),
                "Line_Status": "EXCESS",
                "Comment": "surplus",
            },
        ]
        self.summary = {
            "OK": 1,
            "SHORT": 0,
            "EXCESS": 1,
            "NOT_COUNTED": 1,
            "UNKNOWN": 0,
            "Estimated_Variance_Value": Decimal("12.50"),
        }
        self.line_requests = []
        self.summary_requests = []
        self.scan_calls = []

    def get_sessions(self, status=None, limit=100):
        if status:
            return [session for session in self.sessions if session["Status"] == status]
        return self.sessions[:limit]

    def get_session_lines(self, session_id, status=None, search=None):
        self.line_requests.append((session_id, status, search))
        lines = list(self.lines)
        if status:
            lines = [line for line in lines if line.get("Line_Status") == status]
        if search:
            needle = search.lower()
            lines = [
                line for line in lines
                if needle in (line.get("Product_Name") or "").lower()
                or needle in (line.get("Internal_Barcode") or "").lower()
                or needle in (line.get("Product_Barcode") or "").lower()
            ]
        return lines

    def get_session_summary(self, session_id):
        self.summary_requests.append(session_id)
        return dict(self.summary)

    def get_session_line_by_barcode(self, session_id, barcode):
        normalized = str(barcode or "").strip().lower()
        for line in self.lines:
            values = [
                line.get("Internal_Barcode"),
                line.get("Product_Barcode"),
                line.get("Manuf_Cat_No"),
            ]
            if normalized in {str(value or "").strip().lower() for value in values}:
                return dict(line)
        return None

    def scan_barcode(self, session_id, barcode, qty=1, user_id=None, replace_counted=False):
        self.scan_calls.append(
            {
                "session_id": session_id,
                "barcode": barcode,
                "qty": qty,
                "user_id": user_id,
                "replace_counted": replace_counted,
            }
        )
        line = self.get_session_line_by_barcode(session_id, barcode)
        if not line:
            return {
                "success": True,
                "status": "UNKNOWN",
                "message": "Code inconnu",
                "line": {
                    "Product_Name": "Inconnu",
                    "Internal_Barcode": barcode,
                    "Program_Qty_Snapshot": Decimal("0"),
                    "Counted_Qty": Decimal(str(qty)),
                    "Difference_Qty": Decimal(str(qty)),
                    "Line_Status": "UNKNOWN",
                },
            }

        counted = Decimal(str(qty))
        snapshot = Decimal(str(line["Program_Qty_Snapshot"]))
        line["Counted_Qty"] = counted
        line["Difference_Qty"] = counted - snapshot
        line["Line_Status"] = "OK" if line["Difference_Qty"] == 0 else "SHORT"
        return {"success": True, "status": "MATCHED", "message": "Code trouve", "line": line}


class FakeDataManager:
    def __init__(self):
        self.inventory_counts = FakeInventoryCounts()


class InventoryCountUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        self.app.processEvents()

    def test_inventory_tab_loads_sessions_lines_and_summary(self):
        data_manager = FakeDataManager()
        user = {
            "User_ID": 7,
            "Permissions": [
                "act_inventory_create",
                "act_inventory_scan",
                "act_inventory_apply",
                "act_inventory_cancel",
                "act_inventory_export",
            ],
        }

        tab = InventoryCountTab(data_manager, user)
        tab.sessions_table.selectRow(0)
        tab.load_current_session()

        self.assertEqual(tab.sessions_table.rowCount(), 2)
        self.assertEqual(tab.current_session_id, 101)
        self.assertEqual(tab.lines_table.rowCount(), 2)
        self.assertEqual(tab.lines_table.item(0, 0).text(), "Glucose")
        self.assertEqual(tab.summary_cards["OK"].value_label.text(), "1")
        self.assertEqual(tab.summary_cards["EXCESS"].value_label.text(), "1")
        self.assertTrue(tab.btn_scan.isEnabled())
        tab.deleteLater()

    def test_inventory_tab_hides_buttons_without_action_permissions(self):
        tab = InventoryCountTab(FakeDataManager(), {"User_ID": 7, "Permissions": []})

        self.assertTrue(tab.btn_new.isHidden())
        self.assertTrue(tab.btn_scan.isHidden())
        self.assertTrue(tab.btn_apply.isHidden())
        self.assertTrue(tab.btn_cancel.isHidden())
        self.assertTrue(tab.btn_export.isHidden())
        self.assertFalse(tab.btn_refresh.isHidden())
        tab.deleteLater()

    def test_inventory_tab_button_state_follows_applied_session(self):
        user = {
            "User_ID": 7,
            "Permissions": [
                "act_inventory_scan",
                "act_inventory_apply",
                "act_inventory_cancel",
                "act_inventory_export",
            ],
        }
        tab = InventoryCountTab(FakeDataManager(), user)
        tab.sessions_table.selectRow(1)
        tab.load_current_session()

        self.assertEqual(tab.current_session_id, 102)
        self.assertFalse(tab.btn_scan.isEnabled())
        self.assertFalse(tab.btn_apply.isEnabled())
        self.assertFalse(tab.btn_cancel.isEnabled())
        self.assertTrue(tab.btn_export.isEnabled())
        tab.deleteLater()

    def test_scan_dialog_loads_known_product_and_records_quantity(self):
        data_manager = FakeDataManager()
        dialog = InventoryCountScanDialog(data_manager, 101, {"User_ID": 7})
        emitted = []
        dialog.scan_recorded.connect(lambda: emitted.append(True))

        dialog.barcode_input.setText("INT-001")
        dialog.load_barcode_details()

        self.assertEqual(dialog.pending_line["Product_Name"], "Glucose")
        self.assertEqual(dialog.product_title_label.text(), "Glucose")
        self.assertEqual(dialog.qty_input.value(), 10)

        dialog.qty_input.setValue(7)
        dialog.record_current_quantity()

        self.assertEqual(len(data_manager.inventory_counts.scan_calls), 1)
        self.assertTrue(data_manager.inventory_counts.scan_calls[0]["replace_counted"])
        self.assertEqual(data_manager.inventory_counts.scan_calls[0]["qty"], 7)
        self.assertEqual(dialog.scan_table.rowCount(), 1)
        self.assertEqual(dialog.scan_table.item(0, 0).text(), "INT-001")
        self.assertEqual(dialog.scan_table.item(0, 2).text(), "MATCHED")
        self.assertEqual(dialog.barcode_input.text(), "")
        self.assertEqual(emitted, [True])
        dialog.deleteLater()

    def test_scan_dialog_unknown_barcode_keeps_manual_quantity_flow(self):
        dialog = InventoryCountScanDialog(FakeDataManager(), 101, {"User_ID": 7})

        dialog.barcode_input.setText("UNKNOWN-777")
        dialog.load_barcode_details()

        self.assertIsNone(dialog.pending_line)
        self.assertEqual(dialog.product_title_label.text(), "Inconnu")
        self.assertEqual(dialog.detail_labels["Internal_Barcode"].text(), "UNKNOWN-777")
        self.assertEqual(dialog.qty_input.value(), 1)
        self.assertIn("UNKNOWN", dialog.result_label.text())
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
