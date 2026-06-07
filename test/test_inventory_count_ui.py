import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ui.widgets.inventory import inventory_count_tab as tab_module
from ui.widgets.inventory.inventory_count_scan_dialog import InventoryCountScanDialog
from ui.widgets.inventory.inventory_count_tab import InventoryCountTab, NewInventorySessionDialog


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
        self.created_sessions = []
        self.mark_review_calls = []
        self.cancel_calls = []
        self.apply_calls = []
        self.export_calls = []
        self.create_result = 103
        self.mark_review_result = True
        self.cancel_result = {"success": True, "message": "Session annulee."}
        self.apply_result = {"success": True, "message": "Inventaire applique.", "conflicts": []}
        self.export_result = {"success": True, "message": "Export termine."}

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

    def create_session(self, name, scope_type="ALL", scope_id=None, created_by=None, notes=None):
        self.created_sessions.append(
            {
                "name": name,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "created_by": created_by,
                "notes": notes,
            }
        )
        if self.create_result:
            self.sessions.insert(
                0,
                {
                    "Session_ID": self.create_result,
                    "Session_Name": name,
                    "Status": "Counting",
                    "Started_At": "2026-06-07 10:00:00",
                    "Created_By": created_by,
                },
            )
        return self.create_result

    def mark_review(self, session_id):
        self.mark_review_calls.append(session_id)
        return self.mark_review_result

    def cancel_session(self, session_id, user_id=None):
        self.cancel_calls.append((session_id, user_id))
        return self.cancel_result

    def apply_session(self, session_id, user_id=None, allow_unknown=False):
        self.apply_calls.append((session_id, user_id, allow_unknown))
        return self.apply_result

    def export_session_to_excel(self, session_id, output_path):
        self.export_calls.append((session_id, output_path))
        return self.export_result


class FakeLocations:
    def get_all_locations(self):
        return [
            {"Location_ID": 1, "Location_Name": "Stock A"},
            {"Location_ID": None, "Location_Name": "Ignored"},
        ]


class FakeFamilies:
    def get_all_families(self):
        return [
            {"Family_ID": 2, "Family_Name": "Biochimie"},
            {"Family_ID": None, "Family_Name": "Ignored"},
        ]


class FakeProducts:
    def __init__(self):
        self.searches = []

    def search_products(self, search_text, limit=80):
        self.searches.append((search_text, limit))
        return [
            {
                "Product_ID": 3,
                "Product_Name": "Glucose",
                "Family_Name": "Biochimie",
                "Barcode": "PROD-001",
            },
            {
                "Product_ID": None,
                "Product_Name": "Ignored",
            },
        ]


class FakeDataManager:
    def __init__(self):
        self.inventory_counts = FakeInventoryCounts()
        self.locations = FakeLocations()
        self.families = FakeFamilies()
        self.products = FakeProducts()


class FakeMessageBox:
    def __init__(self, question_results=None):
        self.warnings = []
        self.informations = []
        self.questions = list(question_results or [])

    def warning(self, parent, title, message):
        self.warnings.append((title, message))
        return QMessageBox.Ok

    def information(self, parent, title, message):
        self.informations.append((title, message))
        return QMessageBox.Ok

    def question(self, parent, title, message, buttons, default):
        self.questions.append((title, message, buttons, default))
        queued = self.questions.pop(0)
        if isinstance(queued, tuple):
            return QMessageBox.Yes
        return queued


class FakeSessionDialog:
    result = QDialog.Accepted
    values_payload = {
        "name": "Session creee",
        "scope_type": "ALL",
        "scope_id": None,
        "notes": None,
    }

    def __init__(self, data_manager, parent=None):
        self.data_manager = data_manager
        self.parent = parent

    def exec(self):
        return self.result

    def values(self):
        return dict(self.values_payload)


class InventoryCountUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        self.app.processEvents()

    def test_new_session_dialog_loads_scope_options_and_product_search(self):
        data_manager = FakeDataManager()
        dialog = NewInventorySessionDialog(data_manager)

        dialog.scope_combo.setCurrentText("LOCATION")
        self.assertTrue(dialog.scope_selector.isEnabled())
        self.assertEqual(dialog.scope_selector.count(), 1)
        dialog.scope_selector.setCurrentIndex(0)
        self.assertEqual(dialog.selected_scope_id(), 1)

        dialog.scope_combo.setCurrentText("FAMILY")
        self.assertEqual(dialog.scope_selector.count(), 1)
        dialog.scope_selector.setCurrentIndex(0)
        self.assertEqual(dialog.selected_scope_id(), 2)

        dialog.scope_combo.setCurrentText("PRODUCT")
        dialog.scope_selector.lineEdit().setText("glu")
        dialog.load_product_scope_options()
        self.assertEqual(data_manager.products.searches, [("glu", 80)])
        self.assertEqual(dialog.scope_selector.count(), 1)
        self.assertIn("Glucose", dialog.scope_selector.itemText(0))
        dialog.scope_selector.setCurrentIndex(0)
        self.assertEqual(dialog.selected_scope_id(), 3)
        dialog.deleteLater()

    def test_has_action_supports_list_dict_json_and_invalid_json(self):
        tab_list = InventoryCountTab(FakeDataManager(), {"Permissions": ["act_inventory_scan"]})
        tab_dict = InventoryCountTab(FakeDataManager(), {"Permissions": {"act_inventory_scan": True}})
        tab_json = InventoryCountTab(FakeDataManager(), {"Permissions": '{"act_inventory_scan": true}'})
        tab_bad_json = InventoryCountTab(FakeDataManager(), {"Permissions": "{bad json"})

        self.assertTrue(tab_list.has_action("act_inventory_scan"))
        self.assertTrue(tab_dict.has_action("act_inventory_scan"))
        self.assertTrue(tab_json.has_action("act_inventory_scan"))
        self.assertFalse(tab_bad_json.has_action("act_inventory_scan"))
        tab_list.deleteLater()
        tab_dict.deleteLater()
        tab_json.deleteLater()
        tab_bad_json.deleteLater()

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

    def test_inventory_tab_filters_lines_by_status_and_search(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"Permissions": []})
        tab.sessions_table.selectRow(0)
        tab.load_current_session()

        tab.status_filter.setCurrentText("EXCESS")
        tab.search_input.setText("control")
        tab.load_lines()

        self.assertIn((101, "EXCESS", "control"), data_manager.inventory_counts.line_requests)
        self.assertEqual(tab.lines_table.rowCount(), 1)
        self.assertEqual(tab.lines_table.item(0, 0).text(), "Controle")
        tab.deleteLater()

    def test_inventory_tab_load_sessions_without_manager_warns_and_clears(self):
        data_manager = FakeDataManager()
        data_manager.inventory_counts = None
        messages = FakeMessageBox()

        with patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab = InventoryCountTab(data_manager, {"Permissions": []})

        self.assertEqual(tab.sessions_table.rowCount(), 0)
        self.assertEqual(tab.lines_table.rowCount(), 0)
        self.assertEqual(messages.warnings[0][0], "Inventaire")
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

    def test_inventory_tab_button_state_follows_review_and_no_selection(self):
        data_manager = FakeDataManager()
        data_manager.inventory_counts.sessions[0]["Status"] = "Review"
        tab = InventoryCountTab(
            data_manager,
            {"Permissions": ["act_inventory_scan", "act_inventory_apply", "act_inventory_cancel"]},
        )

        tab._set_buttons_for_session()
        self.assertFalse(tab.btn_scan.isEnabled())
        self.assertFalse(tab.btn_apply.isEnabled())
        self.assertEqual(tab.session_context_label.text(), "Aucune session")

        tab.sessions_table.selectRow(0)
        tab.load_current_session()
        self.assertTrue(tab.btn_scan.isEnabled())
        self.assertTrue(tab.btn_apply.isEnabled())
        self.assertFalse(tab.btn_review.isEnabled())
        self.assertTrue(tab.btn_cancel.isEnabled())
        tab.deleteLater()

    def test_create_session_success_uses_dialog_values_and_selects_new_session(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"User_ID": 7, "Permissions": ["act_inventory_create"]})
        messages = FakeMessageBox()
        FakeSessionDialog.result = QDialog.Accepted
        FakeSessionDialog.values_payload = {
            "name": "Session creee",
            "scope_type": "LOCATION",
            "scope_id": 1,
            "notes": "note",
        }

        with patch.object(tab_module, "NewInventorySessionDialog", FakeSessionDialog), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning), \
             patch.object(tab_module.QMessageBox, "information", messages.information):
            tab.create_session()

        self.assertEqual(
            data_manager.inventory_counts.created_sessions[0],
            {
                "name": "Session creee",
                "scope_type": "LOCATION",
                "scope_id": 1,
                "created_by": 7,
                "notes": "note",
            },
        )
        self.assertEqual(messages.informations[0][0], "Inventaire")
        self.assertEqual(tab.sessions_table.item(0, 0).text(), "103")
        tab.deleteLater()

    def test_create_session_handles_cancel_empty_name_missing_scope_and_failure(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"User_ID": 7, "Permissions": ["act_inventory_create"]})
        messages = FakeMessageBox()

        with patch.object(tab_module, "NewInventorySessionDialog", FakeSessionDialog), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            FakeSessionDialog.result = QDialog.Rejected
            tab.create_session()
            self.assertEqual(data_manager.inventory_counts.created_sessions, [])

            FakeSessionDialog.result = QDialog.Accepted
            FakeSessionDialog.values_payload = {"name": "", "scope_type": "ALL", "scope_id": None, "notes": None}
            tab.create_session()
            self.assertIn("obligatoire", messages.warnings[-1][1])

            FakeSessionDialog.values_payload = {
                "name": "Bad scope",
                "scope_type": "LOCATION",
                "scope_id": None,
                "notes": None,
            }
            tab.create_session()
            self.assertIn("scope", messages.warnings[-1][1])

            data_manager.inventory_counts.create_result = None
            FakeSessionDialog.values_payload = {
                "name": "Create fail",
                "scope_type": "ALL",
                "scope_id": None,
                "notes": None,
            }
            tab.create_session()
            self.assertIn("Impossible", messages.warnings[-1][1])

        tab.deleteLater()

    def test_mark_review_success_and_failure_refreshes_session(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"Permissions": []})
        tab.sessions_table.selectRow(0)
        tab.load_current_session()
        messages = FakeMessageBox()

        with patch.object(tab_module.QMessageBox, "information", messages.information), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab.mark_review()
            data_manager.inventory_counts.mark_review_result = False
            tab.sessions_table.selectRow(0)
            tab.load_current_session()
            tab.mark_review()

        self.assertEqual(data_manager.inventory_counts.mark_review_calls, [101, 101])
        self.assertEqual(len(messages.informations), 1)
        self.assertEqual(len(messages.warnings), 1)
        tab.deleteLater()

    def test_cancel_session_confirms_and_calls_manager(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"User_ID": 7, "Permissions": ["act_inventory_cancel"]})
        tab.sessions_table.selectRow(0)
        tab.load_current_session()
        messages = FakeMessageBox([QMessageBox.No, QMessageBox.Yes])

        with patch.object(tab_module.QMessageBox, "question", messages.question), \
             patch.object(tab_module.QMessageBox, "information", messages.information), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab.cancel_session()
            self.assertEqual(data_manager.inventory_counts.cancel_calls, [])
            tab.cancel_session()

        self.assertEqual(data_manager.inventory_counts.cancel_calls, [(101, 7)])
        self.assertEqual(len(messages.informations), 1)
        tab.deleteLater()

    def test_apply_session_handles_unknown_confirmation_success_and_failure(self):
        data_manager = FakeDataManager()
        data_manager.inventory_counts.summary["UNKNOWN"] = 1
        tab = InventoryCountTab(data_manager, {"User_ID": 7, "Permissions": ["act_inventory_apply"]})
        tab.sessions_table.selectRow(0)
        tab.load_current_session()
        messages = FakeMessageBox([QMessageBox.No, QMessageBox.Yes, QMessageBox.Yes, QMessageBox.Yes])

        with patch.object(tab_module.QMessageBox, "question", messages.question), \
             patch.object(tab_module.QMessageBox, "information", messages.information), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab.apply_session()
            self.assertEqual(data_manager.inventory_counts.apply_calls, [])

            tab.apply_session()
            self.assertEqual(data_manager.inventory_counts.apply_calls[-1], (101, 7, True))

            data_manager.inventory_counts.apply_result = {
                "success": False,
                "message": "Conflit",
                "conflicts": [{"Batch_ID": 1}],
            }
            tab.sessions_table.selectRow(0)
            tab.load_current_session()
            tab.apply_session()

        self.assertEqual(len(messages.informations), 1)
        self.assertTrue(any("Conflits: 1" in warning[1] for warning in messages.warnings))
        tab.deleteLater()

    def test_export_session_adds_xlsx_extension_and_reports_result(self):
        data_manager = FakeDataManager()
        tab = InventoryCountTab(data_manager, {"Permissions": ["act_inventory_export"]})
        tab.sessions_table.selectRow(0)
        tab.load_current_session()
        messages = FakeMessageBox()

        with patch.object(tab_module.QFileDialog, "getSaveFileName", return_value=("C:/tmp/inventaire", "")), \
             patch.object(tab_module.QMessageBox, "information", messages.information), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab.export_session()

        self.assertEqual(data_manager.inventory_counts.export_calls, [(101, "C:/tmp/inventaire.xlsx")])
        self.assertEqual(len(messages.informations), 1)

        data_manager.inventory_counts.export_result = {"success": False, "message": "Export impossible."}
        with patch.object(tab_module.QFileDialog, "getSaveFileName", return_value=("C:/tmp/inventaire.xlsx", "")), \
             patch.object(tab_module.QMessageBox, "information", messages.information), \
             patch.object(tab_module.QMessageBox, "warning", messages.warning):
            tab.export_session()

        self.assertEqual(len(messages.warnings), 1)
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

    def test_scan_dialog_fallback_matches_compact_product_codes(self):
        data_manager = FakeDataManager()
        data_manager.inventory_counts.get_session_line_by_barcode = None
        data_manager.inventory_counts.get_session_lines = (
            lambda session_id, status=None, search=None: data_manager.inventory_counts.lines
        )
        dialog = InventoryCountScanDialog(data_manager, 101, {"User_ID": 7})

        line = dialog._find_line_for_barcode("PROD 001")

        self.assertIsNotNone(line)
        self.assertEqual(line["Product_Name"], "Glucose")
        dialog.deleteLater()

    def test_scan_dialog_schedule_lookup_and_row_limit(self):
        dialog = InventoryCountScanDialog(FakeDataManager(), 101, {"User_ID": 7})
        dialog.pending_barcode = "old"
        dialog.pending_line = {"Line_ID": 1}
        dialog.last_loaded_barcode = "old"

        dialog.schedule_barcode_lookup("")
        self.assertEqual(dialog.pending_barcode, "")
        self.assertIsNone(dialog.pending_line)
        self.assertEqual(dialog.last_loaded_barcode, "")

        dialog.schedule_barcode_lookup("ab")
        self.assertFalse(dialog.barcode_lookup_timer.isActive())

        for index in range(25):
            dialog._prepend_scan_row(f"B{index}", 1, "MATCHED", "ok")

        self.assertEqual(dialog.scan_table.rowCount(), 20)
        self.assertEqual(dialog.scan_table.item(0, 0).text(), "B24")
        dialog.deleteLater()

    def test_scan_dialog_handles_missing_manager_and_exceptions(self):
        data_manager = FakeDataManager()
        data_manager.inventory_counts = None
        dialog = InventoryCountScanDialog(data_manager, 101, {"User_ID": 7})

        dialog.barcode_input.setText("ABC-123")
        dialog.load_barcode_details()
        self.assertIn("ERROR", dialog.result_label.text())

        dialog.record_current_quantity()
        self.assertEqual(dialog.scan_table.item(0, 2).text(), "ERROR")
        dialog.deleteLater()

        class RaisingInventoryCounts(FakeInventoryCounts):
            def get_session_line_by_barcode(self, session_id, barcode):
                raise RuntimeError("lookup boom")

            def scan_barcode(self, *args, **kwargs):
                raise RuntimeError("scan boom")

        data_manager = FakeDataManager()
        data_manager.inventory_counts = RaisingInventoryCounts()
        dialog = InventoryCountScanDialog(data_manager, 101, {"User_ID": 7})
        dialog.barcode_input.setText("ABC-123")
        dialog.load_barcode_details()
        self.assertIn("lookup boom", dialog.result_label.text())

        dialog.pending_barcode = "ABC-123"
        dialog.record_current_quantity()
        self.assertEqual(dialog.scan_table.item(0, 2).text(), "ERROR")
        self.assertIn("scan boom", dialog.scan_table.item(0, 4).text())
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
