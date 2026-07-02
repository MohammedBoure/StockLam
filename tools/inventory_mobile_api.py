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
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXED_API_TOKEN = "StockLam-Inventaire-Mobile-2026"
import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import Database, LabDataManager  # noqa: E402


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
                self._send_json(HTTPStatus.OK, {"success": True, "app": "StockLam", "service": "inventory_mobile_api"})
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


def build_server(host: str, port: int, data_manager=None):
    if data_manager is None:
        db = Database()
        data_manager = LabDataManager(db)
    server = ThreadingHTTPServer((host, port), InventoryMobileApi)
    server.data_manager = data_manager  # type: ignore[attr-defined]
    return server


def main():
    parser = argparse.ArgumentParser(description="StockLam mobile inventory scanner API")
    parser.add_argument("--host", default=os.getenv("INVENTORY_MOBILE_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("INVENTORY_MOBILE_API_PORT", "8787")))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = build_server(args.host, args.port)
    logging.info("Inventory mobile API listening on http://%s:%s", args.host, args.port)
    logging.info("Built-in mobile app key protection is enabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping inventory mobile API.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
