# api/services/inventory_count_service.py
"""Inventory count session service for mobile inventory auditing."""

from typing import Any, Dict, List, Optional


def clean_line(line: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Nettoie les champs de ligne de session pour l'exposition API."""
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


def get_sessions(data_manager: Any, status: Optional[str] = "Counting", limit: int = 50) -> List[Dict[str, Any]]:
    """Récupère les sessions d'inventaire actives."""
    try:
        return data_manager.inventory_counts.get_sessions(status=status, limit=limit)
    except Exception:
        return []


def get_session_summary(data_manager: Any, session_id: int) -> Dict[str, Any]:
    """Récupère le résumé chiffré d'une session d'inventaire."""
    try:
        return data_manager.inventory_counts.get_session_summary(session_id) or {}
    except Exception:
        return {}


def get_session_line(data_manager: Any, session_id: int, barcode: str) -> Optional[Dict[str, Any]]:
    """Recherche une ligne de comptage par code-barres dans une session."""
    try:
        line = data_manager.inventory_counts.get_session_line_by_barcode(session_id, barcode)
        return clean_line(line)
    except Exception:
        return None


def scan_session_barcode(
    data_manager: Any,
    session_id: int,
    barcode: str,
    qty: float = 1,
    user_id: Optional[int] = None,
    replace_counted: bool = True,
) -> Dict[str, Any]:
    """Enregistre un comptage de lot dans une session d'inventaire."""
    try:
        result = data_manager.inventory_counts.scan_barcode(
            session_id, barcode, qty, user_id, replace_counted=replace_counted
        )
        result = dict(result)
        result["line"] = clean_line(result.get("line"))
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}
