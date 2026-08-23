# test/test_inventory_mobile_api.py

import json
import socket
import threading
import unittest
from datetime import date, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api import (
    DISCOVERY_REQUEST,
    FIXED_API_TOKEN,
    build_discovery_server,
    build_server,
)


class MockBatchesManager:
    def __init__(self):
        self.batches = [
            {
                "Batch_ID": 101,
                "Product_ID": 1,
                "Product_Name": "GLUCOSE PAP 500T",
                "Internal_Barcode": "613000101",
                "Barcode": "MAN-GLUC-01",
                "Lot_Number": "LOT-2026-A",
                "Expiry_Date": date.today() + timedelta(days=60),
                "Date_Received": date.today() - timedelta(days=10),
                "Quantity_Current": 10,
                "Location_ID": 1,
                "Location_Name": "Frigo Réactifs A",
                "Family_Name": "Biochimie",
                "Manuf_Name": "Biosystems",
                "Stock_Unit": "Boîte",
                "Minimum_Stock_Level": 5,
            },
            {
                "Batch_ID": 102,
                "Product_ID": 1,
                "Product_Name": "GLUCOSE PAP 500T",
                "Internal_Barcode": "613000102",
                "Barcode": "MAN-GLUC-01",
                "Lot_Number": "LOT-2026-B",
                "Expiry_Date": date.today() + timedelta(days=180),
                "Date_Received": date.today() - timedelta(days=2),
                "Quantity_Current": 15,
                "Location_ID": 2,
                "Location_Name": "Rayon B",
                "Family_Name": "Biochimie",
                "Manuf_Name": "Biosystems",
                "Stock_Unit": "Boîte",
                "Minimum_Stock_Level": 5,
            },
        ]
        self.consumed_logs = []
        self.transferred_logs = []

    def get_all_batches_with_details(self, include_zero_stock=False):
        return [dict(b) for b in self.batches]

    def direct_consume_batch_unit(self, batch_id: int, qty: int = 1, user_id=None, notes=None):
        for b in self.batches:
            if b["Batch_ID"] == batch_id:
                if b["Quantity_Current"] >= qty:
                    b["Quantity_Current"] -= qty
                    self.consumed_logs.append((batch_id, qty, user_id, notes))
                    return True
        return False

    def transfer_batch_location(self, batch_id: int, new_location_id: int, qty: int, user_id=None):
        for b in self.batches:
            if b["Batch_ID"] == batch_id:
                if b["Quantity_Current"] >= qty:
                    self.transferred_logs.append((batch_id, new_location_id, qty, user_id))
                    return True
        return False


class MockLocationsManager:
    def get_all_locations_flat(self):
        return [
            {"Location_ID": 1, "Location_Name": "Labo > Frigo Réactifs A", "Parent_ID": None, "Type_Name": "Frigo"},
            {"Location_ID": 2, "Location_Name": "Labo > Rayon B", "Parent_ID": None, "Type_Name": "Rayonnage"},
            {"Location_ID": 3, "Location_Name": "Biochimie > Automate 1", "Parent_ID": None, "Type_Name": "Paillasse"},
        ]

    def get_location_by_id(self, location_id: int):
        for loc in self.get_all_locations_flat():
            if loc["Location_ID"] == location_id:
                return loc
        return None


class MockFamiliesManager:
    def get_all_families(self):
        return [
            {"Family_ID": 1, "Family_Name": "Biochimie"},
            {"Family_ID": 2, "Family_Name": "Hématologie"},
        ]


class MockProductsManager:
    def get_product_by_barcode(self, barcode: str):
        if barcode == "MAN-GLUC-01":
            return {
                "Product_ID": 1,
                "Product_Name": "GLUCOSE PAP 500T",
                "Barcode": "MAN-GLUC-01",
                "Family_Name": "Biochimie",
                "Manuf_Name": "Biosystems",
                "Stock_Unit": "Boîte",
                "Minimum_Stock_Level": 5,
            }
        return None


class MockInventoryCountsManager:
    def __init__(self):
        self.sessions = [
            {
                "Session_ID": 1,
                "Session_Name": "Inventaire Annuel 2026",
                "Scope_Type": "ALL",
                "Scope_ID": None,
                "Status": "Counting",
                "Created_By": 1,
                "Notes": "Inventaire complet",
                "Started_At": "2026-01-15T08:00:00",
                "Completed_At": None,
                "Applied_At": None,
                "Applied_By": None,
                "Total_Lines": 2,
                "OK_Count": 0,
                "Short_Count": 0,
                "Excess_Count": 0,
                "Not_Counted_Count": 2,
                "Unknown_Count": 0,
                "Location_Name": None,
                "Family_Name": None,
                "Product_Name": None,
            }
        ]
        self.lines = {
            1: [
                {
                    "Line_ID": 10,
                    "Session_ID": 1,
                    "Batch_ID": 101,
                    "Product_ID": 1,
                    "Internal_Barcode": "613000101",
                    "Product_Barcode": "MAN-GLUC-01",
                    "Product_Name": "GLUCOSE PAP 500T",
                    "Lot_Number": "LOT-2026-A",
                    "Expiry_Date": "2026-06-30",
                    "Location_Name": "Frigo Réactifs A",
                    "Program_Qty_Snapshot": 10.0,
                    "Counted_Qty": 0.0,
                    "Difference_Qty": -10.0,
                    "Line_Status": "NOT_COUNTED",
                    "Quantity_Current": 10.0,
                    "Batch_Status": "Available",
                },
                {
                    "Line_ID": 11,
                    "Session_ID": 1,
                    "Batch_ID": 102,
                    "Product_ID": 1,
                    "Internal_Barcode": "613000102",
                    "Product_Barcode": "MAN-GLUC-01",
                    "Product_Name": "GLUCOSE PAP 500T",
                    "Lot_Number": "LOT-2026-B",
                    "Expiry_Date": "2026-10-30",
                    "Location_Name": "Rayon B",
                    "Program_Qty_Snapshot": 15.0,
                    "Counted_Qty": 0.0,
                    "Difference_Qty": -15.0,
                    "Line_Status": "NOT_COUNTED",
                    "Quantity_Current": 15.0,
                    "Batch_Status": "Available",
                },
            ]
        }

    def create_session(self, session_name, scope_type="ALL", scope_id=None, created_by=None, notes=None):
        new_id = len(self.sessions) + 1
        new_sess = {
            "Session_ID": new_id,
            "Session_Name": session_name,
            "Scope_Type": scope_type,
            "Scope_ID": scope_id,
            "Status": "Counting",
            "Created_By": created_by,
            "Notes": notes,
            "Started_At": "2026-08-23T10:00:00",
            "Completed_At": None,
            "Applied_At": None,
            "Applied_By": None,
            "Total_Lines": 0,
            "OK_Count": 0,
            "Short_Count": 0,
            "Excess_Count": 0,
            "Not_Counted_Count": 0,
            "Unknown_Count": 0,
        }
        self.sessions.append(new_sess)
        self.lines[new_id] = []
        return new_id

    def get_sessions(self, status=None, limit=100, year=None):
        res = self.sessions
        if status:
            res = [s for s in res if s["Status"] == status]
        return res[:limit]

    def get_session_summary(self, session_id):
        sess_lines = self.lines.get(session_id, [])
        summary = {
            "Total_Lines": len(sess_lines),
            "OK": sum(1 for l in sess_lines if l["Line_Status"] == "OK"),
            "SHORT": sum(1 for l in sess_lines if l["Line_Status"] == "SHORT"),
            "EXCESS": sum(1 for l in sess_lines if l["Line_Status"] == "EXCESS"),
            "NOT_COUNTED": sum(1 for l in sess_lines if l["Line_Status"] == "NOT_COUNTED"),
            "UNKNOWN": sum(1 for l in sess_lines if l["Line_Status"] == "UNKNOWN"),
            "Estimated_Variance_Value": 0.0,
        }
        return summary

    def get_session_line_by_barcode(self, session_id, barcode):
        for line in self.lines.get(session_id, []):
            if line["Internal_Barcode"] == barcode or line.get("Product_Barcode") == barcode:
                return line
        return None

    def get_session_lines(self, session_id, status=None, search=None):
        res = self.lines.get(session_id, [])
        if status:
            res = [l for l in res if l["Line_Status"] == status]
        if search:
            search_low = search.lower()
            res = [l for l in res if search_low in (l.get("Product_Name") or "").lower() or search_low in (l.get("Internal_Barcode") or "").lower()]
        return res

    def scan_barcode(self, session_id, barcode, qty=1, user_id=None, replace_counted=False):
        for line in self.lines.get(session_id, []):
            if line["Internal_Barcode"] == barcode or line.get("Product_Barcode") == barcode:
                line["Counted_Qty"] = float(qty) if replace_counted else float(line["Counted_Qty"]) + float(qty)
                diff = line["Counted_Qty"] - line["Program_Qty_Snapshot"]
                line["Difference_Qty"] = diff
                line["Line_Status"] = "OK" if diff == 0 else ("SHORT" if diff < 0 else "EXCESS")
                return {"success": True, "status": "MATCHED", "message": "Matched", "line": line}
        
        # Unknown line
        new_line = {
            "Line_ID": 999,
            "Session_ID": session_id,
            "Batch_ID": None,
            "Product_ID": None,
            "Internal_Barcode": barcode,
            "Program_Qty_Snapshot": 0.0,
            "Counted_Qty": float(qty),
            "Difference_Qty": float(qty),
            "Line_Status": "UNKNOWN",
        }
        self.lines.setdefault(session_id, []).append(new_line)
        return {"success": True, "status": "UNKNOWN", "message": "Unknown barcode", "line": new_line}

    def set_counted_quantity(self, line_id, counted_qty):
        for s_lines in self.lines.values():
            for line in s_lines:
                if line["Line_ID"] == line_id:
                    line["Counted_Qty"] = float(counted_qty)
                    diff = line["Counted_Qty"] - line["Program_Qty_Snapshot"]
                    line["Difference_Qty"] = diff
                    line["Line_Status"] = "OK" if diff == 0 else ("SHORT" if diff < 0 else "EXCESS")
                    return {"success": True, "line": line}
        return False

    def mark_review(self, session_id):
        for s in self.sessions:
            if s["Session_ID"] == session_id:
                s["Status"] = "Review"
                return True
        return False

    def apply_session(self, session_id, user_id=None, allow_unknown=False, uncounted_action="ignore"):
        for s in self.sessions:
            if s["Session_ID"] == session_id:
                s["Status"] = "Applied"
                return {"success": True, "applied_count": len(self.lines.get(session_id, [])), "message": "Applied successfully."}
        return {"success": False, "message": "Session not found."}

    def cancel_session(self, session_id, user_id=None):
        for s in self.sessions:
            if s["Session_ID"] == session_id:
                s["Status"] = "Cancelled"
                return {"success": True, "message": "Session cancelled."}
        return {"success": False, "message": "Session not found."}

    def delete_session(self, session_id):
        for i, s in enumerate(self.sessions):
            if s["Session_ID"] == session_id:
                del self.sessions[i]
                self.lines.pop(session_id, None)
                return True
        return False


class MockDataManager:
    def __init__(self):
        self.batches = MockBatchesManager()
        self.locations = MockLocationsManager()
        self.families = MockFamiliesManager()
        self.products = MockProductsManager()
        self.inventory_counts = MockInventoryCountsManager()


class InventoryMobileApiTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        self.data_manager = MockDataManager()
        self.server = build_server(
            "127.0.0.1",
            0,
            data_manager=self.data_manager,
            remote_scan_callback=self._receive,
            device_name="Test PC",
            device_id="test-pc-1",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _receive(self, barcode):
        self.received.append(barcode)
        return True

    def _json_request(self, path, method="GET", payload=None, token=FIXED_API_TOKEN):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-API-Key"] = token

        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers=headers,
        )
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_advertises_capabilities(self):
        result = self._json_request("/api/health", token=None)
        self.assertTrue(result["success"])
        self.assertEqual(result["device_name"], "Test PC")
        self.assertEqual(result["device_id"], "test-pc-1")
        self.assertTrue(result["remote_input"])
        self.assertIn("safe_consumption", result["capabilities"])
        self.assertIn("safe_transfer", result["capabilities"])
        self.assertIn("barcode_lookup", result["capabilities"])
        self.assertIn("inventory_sessions", result["capabilities"])

    def test_barcode_lookup_resolves_and_marks_fefo(self):
        result = self._json_request("/api/barcode/lookup?barcode=613000101")
        self.assertTrue(result["success"])
        self.assertTrue(result["found"])
        self.assertEqual(result["product"]["Product_Name"], "GLUCOSE PAP 500T")
        self.assertEqual(len(result["batches"]), 2)
        self.assertEqual(result["recommended_batch_id"], 101)
        self.assertTrue(result["batches"][0]["is_recommended"])

    def test_safe_consume_recommended_batch_success(self):
        result = self._json_request(
            "/api/stock/consume",
            method="POST",
            payload={"batch_id": 101, "qty": 2, "user_id": 1},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["qty_consumed"], 2)
        self.assertEqual(result["remaining_qty"], 8)

    def test_safe_consume_fefo_violation_blocked_without_override(self):
        try:
            self._json_request(
                "/api/stock/consume",
                method="POST",
                payload={"batch_id": 102, "qty": 1, "allow_fefo_override": False},
            )
            self.fail("Devrait lever une erreur HTTP 409 Conflict")
        except HTTPError as e:
            self.assertEqual(e.code, 409)
            error_data = json.loads(e.read().decode("utf-8"))
            self.assertFalse(error_data["success"])
            self.assertTrue(error_data["fefo_violation"])
            self.assertEqual(error_data["recommended_batch"]["Batch_ID"], 101)

    def test_safe_consume_fefo_override_allowed(self):
        result = self._json_request(
            "/api/stock/consume",
            method="POST",
            payload={"batch_id": 102, "qty": 1, "allow_fefo_override": True},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["fefo_override_used"])
        self.assertEqual(result["remaining_qty"], 14)

    def test_safe_transfer_success(self):
        result = self._json_request(
            "/api/stock/transfer",
            method="POST",
            payload={"batch_id": 101, "target_location_id": 3, "qty": 5},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["qty_transferred"], 5)
        self.assertEqual(result["target_location_id"], 3)

    def test_locations_list(self):
        result = self._json_request("/api/locations")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["locations"]), 3)
        self.assertEqual(result["locations"][0]["Location_Name"], "Labo > Frigo Réactifs A")

    def test_inventory_scopes(self):
        result = self._json_request("/api/inventory-scopes")
        self.assertTrue(result["success"])
        self.assertIn("scopes", result)
        self.assertEqual(len(result["scopes"]["locations"]), 3)
        self.assertEqual(len(result["scopes"]["families"]), 2)

    def test_inventory_sessions_lifecycle_and_operations(self):
        # 1. List sessions
        res = self._json_request("/api/inventory-sessions?status=Counting")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["sessions"]), 1)
        self.assertEqual(res["sessions"][0]["Session_ID"], 1)

        # 2. Get single session details
        res_sess = self._json_request("/api/inventory-sessions/1")
        self.assertTrue(res_sess["success"])
        self.assertEqual(res_sess["session"]["Session_ID"], 1)

        # 3. Create a new session
        res_create = self._json_request(
            "/api/inventory-sessions",
            method="POST",
            payload={"name": "Test Session Mobile", "scope_type": "LOCATION", "scope_id": 1, "user_id": 1},
        )
        self.assertTrue(res_create["success"])
        session_id = res_create["session_id"]
        self.assertEqual(session_id, 2)

        # 4. Scan a barcode in session 1
        res_scan = self._json_request(
            "/api/inventory-sessions/1/scan",
            method="POST",
            payload={"barcode": "613000101", "qty": 10, "replace_counted": True},
        )
        self.assertTrue(res_scan["success"])
        self.assertEqual(res_scan["status"], "MATCHED")
        self.assertEqual(res_scan["line"]["Line_Status"], "OK")
        self.assertEqual(res_scan["line"]["Counted_Qty"], 10.0)

        # 5. Bulk scan
        res_bulk = self._json_request(
            "/api/inventory-sessions/1/bulk-scan",
            method="POST",
            payload={"scans": [{"barcode": "613000102", "qty": 12, "replace_counted": True}]},
        )
        self.assertTrue(res_bulk["success"])
        self.assertEqual(res_bulk["success_count"], 1)

        # 6. Get lines with status filter
        res_lines = self._json_request("/api/inventory-sessions/1/lines?status=SHORT")
        self.assertTrue(res_lines["success"])
        self.assertEqual(len(res_lines["lines"]), 1)
        self.assertEqual(res_lines["lines"][0]["Line_ID"], 11)

        # 7. Update line quantity manually via PUT
        res_put = self._json_request(
            "/api/inventory-sessions/1/lines/11",
            method="PUT",
            payload={"counted_qty": 15.0},
        )
        self.assertTrue(res_put["success"])
        self.assertEqual(res_put["line"]["Line_Status"], "OK")

        # 8. Mark Review
        res_rev = self._json_request(
            "/api/inventory-sessions/1/review",
            method="POST",
        )
        self.assertTrue(res_rev["success"])

        # 9. Apply session
        res_apply = self._json_request(
            "/api/inventory-sessions/1/apply",
            method="POST",
            payload={"user_id": 1},
        )
        self.assertTrue(res_apply["success"])

        # 10. Delete session 2
        res_del = self._json_request(
            "/api/inventory-sessions/2",
            method="DELETE",
        )
        self.assertTrue(res_del["success"])

    def test_remote_scan_calls_desktop_bridge(self):
        result = self._json_request(
            "/api/remote-scans",
            method="POST",
            payload={"barcode": "6130001234567"},
        )
        self.assertEqual(result["status"], "SENT")
        self.assertEqual(self.received, ["6130001234567"])

    def test_udp_discovery_returns_desktop_identity(self):
        discovery = build_discovery_server(
            "127.0.0.1",
            0,
            self.server.server_address[1],
            device_name="Test PC",
            device_id="test-pc-1",
        )
        port = discovery._socket.getsockname()[1]
        thread = threading.Thread(target=discovery.serve_forever, daemon=True)
        thread.start()
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2)
        try:
            client.sendto(DISCOVERY_REQUEST, ("127.0.0.1", port))
            payload, _ = client.recvfrom(2048)
            result = json.loads(payload.decode("utf-8"))
            self.assertEqual(result["app"], "StockLam")
            self.assertEqual(result["device_name"], "Test PC")
            self.assertEqual(result["api_port"], self.server.server_address[1])
        finally:
            client.close()
            discovery.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

