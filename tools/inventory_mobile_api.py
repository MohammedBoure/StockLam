"""Small LAN API for mobile inventory count scanning.

Run on the main PC while StockLam uses the same database:
    venv/Scripts/python.exe tools/inventory_mobile_api.py --host 0.0.0.0 --port 8787

The mobile app sends a built-in StockLam API key automatically.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXED_API_TOKEN = "StockLam-Inventaire-Mobile-2026"
DISCOVERY_PORT = 8788
DISCOVERY_REQUEST = b"STOCKLAM_DISCOVER_V1"
import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def _json_default(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _clean_line(line: dict | None) -> dict | None:
    if not line:
        return None
    wanted = [
        "Line_ID",
        "Session_ID",
        "Batch_ID",
        "Product_ID",
        "Internal_Barcode",
        "Product_Barcode",
        "Product_Name",
        "Manuf_Cat_No",
        "Family_Name",
        "Manuf_Name",
        "Automate_Name",
        "Lot_Number",
        "Expiry_Date",
        "Location_Name",
        "Program_Qty_Snapshot",
        "Counted_Qty",
        "Difference_Qty",
        "Line_Status",
        "Quantity_Current",
        "Batch_Status",
    ]
    return {key: line.get(key) for key in wanted if key in line}


class InventoryMobileApi(BaseHTTPRequestHandler):
    server_version = "StockLamInventoryMobile/1.0"

    def _manager(self):
        return self.server.data_manager.inventory_counts  # type: ignore[attr-defined]

    def _token(self):
        return FIXED_API_TOKEN

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json(status, {"success": False, "message": message})

    def _is_authorized(self):
        token = self._token()
        if not token:
            return True
        return self.headers.get("X-API-Key", "") == token

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _parse_session_route(self, path: str):
        parts = [part for part in path.split("/") if part]
        if len(parts) < 3 or parts[0] != "api" or parts[1] != "inventory-sessions":
            return None, None
        try:
            session_id = int(parts[2])
        except (TypeError, ValueError):
            return None, None
        action = parts[3] if len(parts) > 3 else None
        return session_id, action

    def do_OPTIONS(self):
        self._send_json(HTTPStatus.OK, {"success": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "app": "StockLam",
                    "service": "inventory_mobile_api",
                    "device_name": self.server.device_name,  # type: ignore[attr-defined]
                    "device_id": self.server.device_id,  # type: ignore[attr-defined]
                    "remote_input": callable(getattr(self.server, "remote_scan_callback", None)),
                })
                return

            if not self._is_authorized():
                self._send_error(HTTPStatus.UNAUTHORIZED, "Invalid mobile app key.")
                return

            if path == "/api/inventory-sessions":
                status = query.get("status", ["Counting"])[0] or None
                limit = int(query.get("limit", ["50"])[0] or 50)
                sessions = self._manager().get_sessions(status=status, limit=limit)
                self._send_json(HTTPStatus.OK, {"success": True, "sessions": sessions})
                return

            session_id, action = self._parse_session_route(path)
            if session_id and action == "summary":
                summary = self._manager().get_session_summary(session_id)
                self._send_json(HTTPStatus.OK, {"success": True, "summary": summary})
                return

            if session_id and action == "lookup":
                barcode = (query.get("barcode", [""])[0] or "").strip()
                if not barcode:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Barcode is required.")
                    return
                line = self._manager().get_session_line_by_barcode(session_id, barcode)
                self._send_json(HTTPStatus.OK, {"success": True, "line": _clean_line(line)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
        except Exception as exc:  # Keep the mobile app from receiving HTML tracebacks.
            logging.exception("Inventory mobile API GET failed")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def do_POST(self):
        if not self._is_authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "Invalid mobile app key.")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/remote-scans":
            try:
                data = self._read_body()
                barcode = str(data.get("barcode") or "").strip()
                if not barcode:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Barcode is required.")
                    return
                callback = getattr(self.server, "remote_scan_callback", None)
                if not callable(callback):
                    self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Desktop barcode input is not available.")
                    return
                logging.info("Remote barcode received from mobile: %s", barcode)
                accepted = callback(barcode)
                logging.info("Remote barcode desktop callback result: accepted=%s barcode=%s", accepted, barcode)
                if accepted is False:
                    self._send_error(HTTPStatus.CONFLICT, "Desktop rejected the barcode.")
                    return
                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "status": "SENT",
                    "barcode": barcode,
                    "message": "Barcode sent to the StockLam desktop application.",
                })
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body.")
            except Exception as exc:
                logging.exception("Remote barcode delivery failed")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        session_id, action = self._parse_session_route(path)
        if not session_id or action != "scan":
            self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        try:
            data = self._read_body()
            barcode = str(data.get("barcode") or "").strip()
            qty = data.get("qty", 1)
            user_id = data.get("user_id")
            replace_counted = bool(data.get("replace_counted", True))
            result = self._manager().scan_barcode(session_id, barcode, qty, user_id, replace_counted=replace_counted)
            result = dict(result)
            result["line"] = _clean_line(result.get("line"))
            http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
            self._send_json(http_status, result)
        except json.JSONDecodeError:
            self._send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body.")
        except Exception as exc:
            logging.exception("Inventory mobile API POST failed")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))


def _device_identity():
    name = socket.gethostname() or "StockLam PC"
    return name, f"{name}-{uuid.getnode():012x}"


class InventoryDiscoveryServer:
    """Small UDP responder used by the phone to find StockLam PCs on the LAN."""

    def __init__(self, host: str, port: int, api_port: int, device_name: str, device_id: str):
        self.host = host
        self.port = int(port)
        self.api_port = int(api_port)
        self.device_name = device_name
        self.device_id = device_id
        self._stopped = threading.Event()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, self.port))
        self._socket.settimeout(0.5)

    def serve_forever(self):
        while not self._stopped.is_set():
            try:
                payload, address = self._socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if payload.strip() != DISCOVERY_REQUEST:
                continue
            response = json.dumps({
                "app": "StockLam",
                "service": "inventory_mobile_api",
                "device_name": self.device_name,
                "device_id": self.device_id,
                "api_port": self.api_port,
            }, ensure_ascii=False).encode("utf-8")
            try:
                self._socket.sendto(response, address)
            except OSError:
                logging.debug("Unable to answer StockLam discovery request", exc_info=True)

    def shutdown(self):
        self._stopped.set()
        self._socket.close()

    def server_close(self):
        self.shutdown()


def build_discovery_server(host: str, port: int, api_port: int, device_name=None, device_id=None):
    default_name, default_id = _device_identity()
    return InventoryDiscoveryServer(
        host,
        port,
        api_port,
        device_name or default_name,
        device_id or default_id,
    )


def build_server(host: str, port: int, data_manager=None, remote_scan_callback=None, device_name=None, device_id=None):
    if data_manager is None:
        from database import Database, LabDataManager

        db = Database()
        data_manager = LabDataManager(db)
    default_name, default_id = _device_identity()
    server = ThreadingHTTPServer((host, port), InventoryMobileApi)
    server.data_manager = data_manager  # type: ignore[attr-defined]
    server.remote_scan_callback = remote_scan_callback  # type: ignore[attr-defined]
    server.device_name = device_name or default_name  # type: ignore[attr-defined]
    server.device_id = device_id or default_id  # type: ignore[attr-defined]
    return server


def main():
    parser = argparse.ArgumentParser(description="StockLam mobile inventory scanner API")
    parser.add_argument("--host", default=os.getenv("INVENTORY_MOBILE_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("INVENTORY_MOBILE_API_PORT", "8787")))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = build_server(args.host, args.port)
    discovery_server = None
    discovery_thread = None
    try:
        discovery_server = build_discovery_server(
            args.host,
            int(os.getenv("INVENTORY_MOBILE_DISCOVERY_PORT", str(DISCOVERY_PORT))),
            args.port,
            device_name=server.device_name,  # type: ignore[attr-defined]
            device_id=server.device_id,  # type: ignore[attr-defined]
        )
        discovery_thread = threading.Thread(
            target=discovery_server.serve_forever,
            name="InventoryMobileDiscovery",
            daemon=True,
        )
        discovery_thread.start()
        logging.info("StockLam discovery listening on UDP %s", discovery_server.port)
    except OSError as exc:
        logging.warning("StockLam discovery is unavailable: %s", exc)
    logging.info("Inventory mobile API listening on http://%s:%s", args.host, args.port)
    logging.info("Built-in mobile app key protection is enabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping inventory mobile API.")
    finally:
        if discovery_server is not None:
            discovery_server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
