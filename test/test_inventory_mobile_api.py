import json
import socket
import threading
import unittest
from urllib.request import Request, urlopen

from tools.inventory_mobile_api import (
    DISCOVERY_REQUEST,
    FIXED_API_TOKEN,
    build_discovery_server,
    build_server,
)


class InventoryMobileApiTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        self.server = build_server(
            "127.0.0.1",
            0,
            data_manager=object(),
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

    def _json_request(self, path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": FIXED_API_TOKEN,
            },
        )
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_advertises_desktop_remote_input(self):
        result = self._json_request("/api/health")
        self.assertTrue(result["success"])
        self.assertEqual(result["device_name"], "Test PC")
        self.assertEqual(result["device_id"], "test-pc-1")
        self.assertTrue(result["remote_input"])

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
