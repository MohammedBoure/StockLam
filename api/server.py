# api/server.py
"""HTTP API Server and Request Handler for StockLam Mobile & Barcode Clients."""

from __future__ import annotations

import json
import logging
import socket
import uuid
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .auth import authenticate_user, get_active_users_list, is_request_authorized
from .services.barcode_service import resolve_barcode
from .services.dispatch_service import bulk_dispatch, safe_consume, safe_transfer
from .services.fefo_service import evaluate_fefo_compliance
from .services.inventory_count_service import (
    apply_session,
    bulk_scan_session,
    cancel_session,
    create_session,
    delete_session,
    get_inventory_scopes,
    get_session_by_id,
    get_session_line,
    get_session_lines,
    get_session_summary,
    get_sessions,
    mark_session_review,
    scan_session_barcode,
    update_session_line_quantity,
)
from .services.location_service import get_locations


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _device_identity() -> tuple[str, str]:
    name = socket.gethostname() or "StockLam PC"
    return name, f"{name}-{uuid.getnode():012x}"


class StockLamApiHandler(BaseHTTPRequestHandler):
    server_version = "StockLamAPI/1.1"

    def log_message(self, format, *args):
        logging.info("API HTTP %s - %s", self.client_address[0], format % args)

    @property
    def data_manager(self) -> Any:
        return getattr(self.server, "data_manager", None)

    def _send_json(self, status: int, payload: Dict[str, Any]):
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str, **kwargs):
        payload = {"success": False, "message": message}
        payload.update(kwargs)
        self._send_json(status, payload)

    def _is_authorized(self) -> bool:
        return is_request_authorized(self.headers)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _parse_session_route(self, path: str):
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2 or parts[0] != "api" or parts[1] != "inventory-sessions":
            return None, None, None
        if len(parts) == 2:
            return None, None, None
        try:
            session_id = int(parts[2])
        except (TypeError, ValueError):
            return None, None, None
        action = parts[3] if len(parts) > 3 else None
        sub_id = None
        if len(parts) > 4:
            try:
                sub_id = int(parts[4])
            except (TypeError, ValueError):
                sub_id = parts[4]
        return session_id, action, sub_id

    def do_OPTIONS(self):
        self._send_json(HTTPStatus.OK, {"success": True})

    # =========================================================================
    # GET Endpoints
    # =========================================================================
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            # 1. Health & Capabilities
            if path == "/api/health":
                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "app": "StockLam",
                    "version": "1.1",
                    "service": "stocklam_api",
                    "device_name": getattr(self.server, "device_name", "StockLam PC"),
                    "device_id": getattr(self.server, "device_id", "stocklam-pc"),
                    "remote_input": callable(getattr(self.server, "remote_scan_callback", None)),
                    "capabilities": [
                        "barcode_lookup",
                        "user_auth",
                        "safe_consumption",
                        "safe_transfer",
                        "bulk_dispatch",
                        "fefo_validation",
                        "location_catalog",
                        "remote_scans",
                        "inventory_sessions",
                    ],
                })
                return

            # Vérification de sécurité pour tous les autres points d'accès
            if not self._is_authorized():
                self._send_error(HTTPStatus.UNAUTHORIZED, "Clé API non autorisée (X-API-Key invalide).")
                return

            if not self.data_manager:
                self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Gestionnaire de données StockLam indisponible.")
                return

            # 2. Active Users List (pour la sélection sur mobile)
            if path == "/api/users/list":
                users = get_active_users_list(self.data_manager)
                self._send_json(HTTPStatus.OK, {"success": True, "users": users})
                return

            # 3. Barcode Lookup (Recherche et Détection de produit / lots)
            if path == "/api/barcode/lookup":
                barcode = (query.get("barcode", [""])[0] or "").strip()
                if not barcode:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Le paramètre 'barcode' est obligatoire.")
                    return
                result = resolve_barcode(self.data_manager, barcode)
                self._send_json(HTTPStatus.OK, result)
                return

            # 4. FEFO Compliance Check (Contrôle de conformité FEFO/FIFO)
            if path == "/api/stock/fefo-check":
                batch_id_str = (query.get("batch_id", [""])[0] or "").strip()
                if not batch_id_str.isdigit():
                    self._send_error(HTTPStatus.BAD_REQUEST, "Le paramètre 'batch_id' numérique est obligatoire.")
                    return
                batch_id = int(batch_id_str)
                compliance = evaluate_fefo_compliance(self.data_manager, batch_id)
                rec_batch = compliance.get("recommended_batch")
                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "is_compliant": compliance.get("is_compliant", False),
                    "is_oldest": compliance.get("is_oldest", False),
                    "is_recommended": compliance.get("is_recommended", False),
                    "reason": compliance.get("reason", ""),
                    "recommended_batch_id": compliance.get("recommended_batch_id"),
                    "recommended_batch": {
                        "Batch_ID": rec_batch.get("Batch_ID"),
                        "Lot_Number": rec_batch.get("Lot_Number", "---"),
                        "Expiry_Date": str(rec_batch.get("Expiry_Date") or ""),
                        "Location_Name": rec_batch.get("Location_Name", "---"),
                        "Quantity_Current": float(rec_batch.get("Quantity_Current") or 0) if rec_batch else 0,
                    } if rec_batch else None,
                })
                return

            # 5. Storage Locations List
            if path == "/api/locations":
                locations = get_locations(self.data_manager)
                self._send_json(HTTPStatus.OK, {"success": True, "locations": locations})
                return

            # 6. Inventory Scopes (Locations, Families)
            if path == "/api/inventory-scopes":
                scopes = get_inventory_scopes(self.data_manager)
                self._send_json(HTTPStatus.OK, scopes)
                return

            # 7. Inventory Sessions List
            if path == "/api/inventory-sessions":
                status = query.get("status", [None])[0]
                year = query.get("year", [None])[0]
                limit = int(query.get("limit", ["50"])[0] or 50)
                sessions = get_sessions(self.data_manager, status=status, limit=limit, year=year)
                self._send_json(HTTPStatus.OK, {"success": True, "sessions": sessions})
                return

            # 8. Single Inventory Session & Actions
            session_id, action, sub_id = self._parse_session_route(path)
            if session_id:
                if action is None:
                    session = get_session_by_id(self.data_manager, session_id)
                    if session:
                        self._send_json(HTTPStatus.OK, {"success": True, "session": session})
                    else:
                        self._send_error(HTTPStatus.NOT_FOUND, f"Session #{session_id} introuvable.")
                    return

                if action == "summary":
                    summary = get_session_summary(self.data_manager, session_id)
                    self._send_json(HTTPStatus.OK, {"success": True, "summary": summary})
                    return

                if action == "lookup":
                    barcode = (query.get("barcode", [""])[0] or "").strip()
                    if not barcode:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Le code-barres est obligatoire.")
                        return
                    line = get_session_line(self.data_manager, session_id, barcode)
                    self._send_json(HTTPStatus.OK, {"success": True, "line": line})
                    return

                if action == "lines":
                    line_status = query.get("status", [None])[0]
                    search = query.get("search", [None])[0]
                    lines = get_session_lines(self.data_manager, session_id, status=line_status, search=search)
                    self._send_json(HTTPStatus.OK, {"success": True, "lines": lines})
                    return

            self._send_error(HTTPStatus.NOT_FOUND, "Point d'accès API introuvable.")

        except Exception as exc:
            logging.exception("Erreur inattendue dans l'API StockLam (GET)")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    # =========================================================================
    # POST Endpoints
    # =========================================================================
    def do_POST(self):
        if not self._is_authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "Clé API non autorisée (X-API-Key invalide).")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self.data_manager:
            self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Gestionnaire de données StockLam indisponible.")
            return

        # 1. Authentification utilisateur / Connexion compte
        if path == "/api/auth/login":
            try:
                data = self._read_body()
                username = str(data.get("username") or "").strip()
                password = str(data.get("password") or "").strip()
                if not username or not password:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Nom d'utilisateur et mot de passe obligatoires.")
                    return

                user = authenticate_user(self.data_manager, username, password)
                if not user:
                    self._send_error(HTTPStatus.UNAUTHORIZED, "Nom d'utilisateur ou mot de passe incorrect.")
                    return

                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "message": "Authentification réussie.",
                    "user": user,
                })
            except Exception as exc:
                logging.exception("Erreur lors de l'authentification API")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 2. Pont de Scan Bureau (Desktop Remote Scan Bridge)
        if path == "/api/remote-scans":
            try:
                data = self._read_body()
                barcode = str(data.get("barcode") or "").strip()
                if not barcode:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Le code-barres est obligatoire.")
                    return
                callback = getattr(self.server, "remote_scan_callback", None)
                if not callable(callback):
                    self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "La saisie directe sur bureau est indisponible.")
                    return
                logging.info("Code-barres reçu depuis mobile: %s", barcode)
                accepted = callback(barcode)
                if accepted is False:
                    self._send_error(HTTPStatus.CONFLICT, "L'application bureau a rejeté la saisie du code-barres.")
                    return
                self._send_json(HTTPStatus.OK, {
                    "success": True,
                    "status": "SENT",
                    "barcode": barcode,
                    "message": "Code-barres transmis avec succès à l'application bureau.",
                })
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
            except Exception as exc:
                logging.exception("Erreur lors de la transmission du scan distant")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 3. Consommation directe sécurisée avec vérification FEFO
        if path == "/api/stock/consume":
            try:
                data = self._read_body()
                batch_id = data.get("batch_id")
                barcode = data.get("barcode")
                qty = float(data.get("qty", 1) or 1)
                user_id = data.get("user_id")
                allow_fefo_override = bool(data.get("allow_fefo_override", False))
                notes = data.get("notes")

                # Si le batch_id n'a pas été fourni mais que le code-barres l'est
                if not batch_id and barcode:
                    res_bc = resolve_barcode(self.data_manager, str(barcode))
                    if res_bc.get("found") and res_bc.get("scanned_batch"):
                        batch_id = res_bc["scanned_batch"]["Batch_ID"]
                    elif res_bc.get("found") and res_bc.get("recommended_batch_id"):
                        batch_id = res_bc["recommended_batch_id"]

                if not batch_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Le 'batch_id' (ou un 'barcode' valide) est obligatoire.")
                    return

                result = safe_consume(
                    data_manager=self.data_manager,
                    batch_id=int(batch_id),
                    qty=int(qty),
                    user_id=user_id,
                    allow_fefo_override=allow_fefo_override,
                    notes=notes,
                )

                status_code = HTTPStatus.OK if result.get("success") else (
                    HTTPStatus.CONFLICT if result.get("fefo_violation") else HTTPStatus.BAD_REQUEST
                )
                self._send_json(status_code, result)
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
            except Exception as exc:
                logging.exception("Erreur lors de la consommation directe API")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 4. Transfert d'emplacement sécurisé
        if path == "/api/stock/transfer":
            try:
                data = self._read_body()
                batch_id = data.get("batch_id")
                target_location_id = data.get("target_location_id")
                qty = float(data.get("qty", 1) or 1)
                user_id = data.get("user_id")

                if not batch_id or not target_location_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "'batch_id' et 'target_location_id' sont obligatoires.")
                    return

                result = safe_transfer(
                    data_manager=self.data_manager,
                    batch_id=int(batch_id),
                    target_location_id=int(target_location_id),
                    qty=int(qty),
                    user_id=user_id,
                )

                status_code = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                self._send_json(status_code, result)
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
            except Exception as exc:
                logging.exception("Erreur lors du transfert de lot API")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 5. Saisie Rapide Groupée (Bulk Dispatch / Multi-Produits)
        if path == "/api/stock/bulk-dispatch":
            try:
                data = self._read_body()
                mode = str(data.get("mode") or "consume")
                items = data.get("items") or []
                user_id = data.get("user_id")
                allow_fefo_override = bool(data.get("allow_fefo_override", False))

                result = bulk_dispatch(
                    data_manager=self.data_manager,
                    mode=mode,
                    items=items,
                    user_id=user_id,
                    allow_fefo_override=allow_fefo_override,
                )
                self._send_json(HTTPStatus.OK, result)
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
            except Exception as exc:
                logging.exception("Erreur lors de la saisie groupée multi-produits")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 6. Création de Session d'Inventaire
        if path == "/api/inventory-sessions":
            try:
                data = self._read_body()
                name = str(data.get("name") or data.get("session_name") or "").strip()
                scope_type = str(data.get("scope_type") or "ALL").upper()
                scope_id = data.get("scope_id")
                user_id = data.get("user_id")
                notes = data.get("notes")

                if not name:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Le nom de la session est obligatoire.")
                    return

                result = create_session(
                    data_manager=self.data_manager,
                    name=name,
                    scope_type=scope_type,
                    scope_id=int(scope_id) if scope_id is not None else None,
                    created_by=user_id,
                    notes=notes,
                )
                http_status = HTTPStatus.CREATED if result.get("success") else HTTPStatus.BAD_REQUEST
                self._send_json(http_status, result)
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
            except Exception as exc:
                logging.exception("Erreur lors de la création de session d'inventaire")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 7. Actions sur Sessions d'Inventaire
        session_id, action, sub_id = self._parse_session_route(path)
        if session_id:
            try:
                data = self._read_body()

                # Scan individuel
                if action == "scan":
                    barcode = str(data.get("barcode") or "").strip()
                    qty = float(data.get("qty", 1) or 1)
                    user_id = data.get("user_id")
                    replace_counted = bool(data.get("replace_counted", True))

                    result = scan_session_barcode(
                        data_manager=self.data_manager,
                        session_id=session_id,
                        barcode=barcode,
                        qty=qty,
                        user_id=user_id,
                        replace_counted=replace_counted,
                    )
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

                # Scan groupé (synchronisation hors-ligne)
                if action == "bulk-scan":
                    scans = data.get("scans") or []
                    user_id = data.get("user_id")
                    replace_counted = bool(data.get("replace_counted", False))

                    result = bulk_scan_session(
                        data_manager=self.data_manager,
                        session_id=session_id,
                        scans=scans,
                        user_id=user_id,
                        replace_counted=replace_counted,
                    )
                    self._send_json(HTTPStatus.OK, result)
                    return

                # Modification manuelle de quantité de ligne
                if action == "lines" and sub_id:
                    counted_qty = float(data.get("counted_qty", 0))
                    result = update_session_line_quantity(
                        data_manager=self.data_manager,
                        session_id=session_id,
                        line_id=int(sub_id),
                        counted_qty=counted_qty,
                    )
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

                # Passage en revue
                if action == "review":
                    result = mark_session_review(self.data_manager, session_id)
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

                # Application des écarts au stock réel
                if action == "apply":
                    user_id = data.get("user_id")
                    allow_unknown = bool(data.get("allow_unknown", False))
                    uncounted_action = str(data.get("uncounted_action") or "ignore")

                    result = apply_session(
                        data_manager=self.data_manager,
                        session_id=session_id,
                        user_id=user_id,
                        allow_unknown=allow_unknown,
                        uncounted_action=uncounted_action,
                    )
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

                # Annulation de session
                if action == "cancel":
                    user_id = data.get("user_id")
                    result = cancel_session(self.data_manager, session_id, user_id=user_id)
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

                # Suppression de session
                if action == "delete":
                    result = delete_session(self.data_manager, session_id)
                    http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                    self._send_json(http_status, result)
                    return

            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
                return
            except Exception as exc:
                logging.exception("Erreur lors du traitement de l'action d'inventaire")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return

        self._send_error(HTTPStatus.NOT_FOUND, "Point d'accès API introuvable.")

    # =========================================================================
    # PUT Endpoints
    # =========================================================================
    def do_PUT(self):
        if not self._is_authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "Clé API non autorisée (X-API-Key invalide).")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self.data_manager:
            self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Gestionnaire de données StockLam indisponible.")
            return

        session_id, action, sub_id = self._parse_session_route(path)
        if session_id and action == "lines" and sub_id:
            try:
                data = self._read_body()
                counted_qty = float(data.get("counted_qty", 0))
                result = update_session_line_quantity(
                    data_manager=self.data_manager,
                    session_id=session_id,
                    line_id=int(sub_id),
                    counted_qty=counted_qty,
                )
                http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                self._send_json(http_status, result)
                return
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Corps JSON invalide.")
                return
            except Exception as exc:
                logging.exception("Erreur lors de la mise à jour de ligne")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return

        self._send_error(HTTPStatus.NOT_FOUND, "Point d'accès API introuvable.")

    # =========================================================================
    # DELETE Endpoints
    # =========================================================================
    def do_DELETE(self):
        if not self._is_authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "Clé API non autorisée (X-API-Key invalide).")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self.data_manager:
            self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Gestionnaire de données StockLam indisponible.")
            return

        session_id, action, sub_id = self._parse_session_route(path)
        if session_id and action is None:
            try:
                result = delete_session(self.data_manager, session_id)
                http_status = HTTPStatus.OK if result.get("success") else HTTPStatus.BAD_REQUEST
                self._send_json(http_status, result)
                return
            except Exception as exc:
                logging.exception("Erreur lors de la suppression de la session d'inventaire")
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return

        self._send_error(HTTPStatus.NOT_FOUND, "Point d'accès API introuvable.")


class StockLamApiServer(ReusableThreadingHTTPServer):
    """Serveur HTTP Threadé StockLam avec support des callbacks et de l'identité système."""

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[BaseHTTPRequestHandler],
        data_manager: Any = None,
        remote_scan_callback: Optional[Callable[[str], bool]] = None,
        device_name: Optional[str] = None,
        device_id: Optional[str] = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        default_name, default_id = _device_identity()
        self.data_manager = data_manager
        self.remote_scan_callback = remote_scan_callback
        self.device_name = device_name or default_name
        self.device_id = device_id or default_id


def build_server(
    host: str,
    port: int,
    data_manager: Any = None,
    remote_scan_callback: Optional[Callable[[str], bool]] = None,
    device_name: Optional[str] = None,
    device_id: Optional[str] = None,
) -> StockLamApiServer:
    """Construit et configure une instance de serveur API StockLam."""
    return StockLamApiServer(
        (host, int(port)),
        StockLamApiHandler,
        data_manager=data_manager,
        remote_scan_callback=remote_scan_callback,
        device_name=device_name,
        device_id=device_id,
    )
