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

    def direct_consume_batch_unit(self, batch_id: int, qty: int = 1, user_id=None):
        for b in self.batches:
            if b["Batch_ID"] == batch_id:
                if b["Quantity_Current"] >= qty:
                    b["Quantity_Current"] -= qty
                    self.consumed_logs.append((batch_id, qty, user_id))
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


class MockDataManager:
    def __init__(self):
        self.batches = MockBatchesManager()
        self.locations = MockLocationsManager()
        self.products = MockProductsManager()
        self.inventory_counts = None


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

    def test_barcode_lookup_resolves_and_marks_fefo(self):
        result = self._json_request("/api/barcode/lookup?barcode=613000101")
        self.assertTrue(result["success"])
        self.assertTrue(result["found"])
        self.assertEqual(result["product"]["Product_Name"], "GLUCOSE PAP 500T")
        self.assertEqual(len(result["batches"]), 2)
        # Lot 101 expire plus tôt (60 jours) que Lot 102 (180 jours) -> doit être recommandé
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
        # Tenter de consommer le lot 102 alors que le lot 101 expire plus tôt
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
        # Consommer le lot 102 avec outrepassement FEFO autorisé
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
