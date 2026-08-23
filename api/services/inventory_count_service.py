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
        "Quantity_Initial",
        "Batch_Status",
        "Stock_Unit",
        "Last_Scanned_At",
    ]
    res = {key: line.get(key) for key in wanted if key in line}
    int_keys = ["Line_ID", "Session_ID", "Batch_ID", "Product_ID"]
    for k in int_keys:
        if res.get(k) is not None:
            try:
                res[k] = int(res[k])
            except (ValueError, TypeError):
                pass
    float_keys = ["Program_Qty_Snapshot", "Counted_Qty", "Difference_Qty", "Quantity_Current", "Quantity_Initial"]
    for k in float_keys:
        if res.get(k) is not None:
            try:
                res[k] = float(res[k])
            except (ValueError, TypeError):
                pass
    return res


def clean_session(session: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Nettoie les champs de session pour l'exposition API."""
    if not session:
        return None
    wanted = [
        "Session_ID",
        "Session_Name",
        "Scope_Type",
        "Scope_ID",
        "Status",
        "Created_By",
        "Notes",
        "Started_At",
        "Completed_At",
        "Applied_At",
        "Applied_By",
        "Total_Lines",
        "OK_Count",
        "Short_Count",
        "Excess_Count",
        "Not_Counted_Count",
        "Unknown_Count",
        "Location_Name",
        "Family_Name",
        "Product_Name",
    ]
    res = {key: session.get(key) for key in wanted if key in session}
    int_keys = [
        "Session_ID",
        "Scope_ID",
        "Created_By",
        "Applied_By",
        "Total_Lines",
        "OK_Count",
        "Short_Count",
        "Excess_Count",
        "Not_Counted_Count",
        "Unknown_Count",
    ]
    for k in int_keys:
        if res.get(k) is not None:
            try:
                res[k] = int(res[k])
            except (ValueError, TypeError):
                pass
    return res


def get_sessions(
    data_manager: Any,
    status: Optional[str] = None,
    limit: int = 50,
    year: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Récupère les sessions d'inventaire avec filtres éventuels."""
    try:
        sessions = data_manager.inventory_counts.get_sessions(status=status, limit=limit, year=year)
        return [clean_session(s) or s for s in sessions]
    except Exception:
        return []


def get_session_by_id(data_manager: Any, session_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les informations détaillées d'une session avec son résumé."""
    try:
        sessions = data_manager.inventory_counts.get_sessions(limit=1000)
        for s in sessions:
            if s.get("Session_ID") == session_id:
                cleaned = clean_session(s) or s
                cleaned["summary"] = get_session_summary(data_manager, session_id)
                return cleaned

        summary = get_session_summary(data_manager, session_id)
        if summary and summary.get("Total_Lines", 0) > 0:
            return {"Session_ID": session_id, "summary": summary}
        return None
    except Exception:
        return None


def create_session(
    data_manager: Any,
    name: str,
    scope_type: str = "ALL",
    scope_id: Optional[int] = None,
    created_by: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée une nouvelle session d'inventaire avec snapshot initial."""
    try:
        session_id = data_manager.inventory_counts.create_session(
            session_name=name,
            scope_type=scope_type,
            scope_id=scope_id,
            created_by=created_by,
            notes=notes,
        )
        if not session_id:
            return {"success": False, "message": "Échec de création de la session d'inventaire."}

        session = get_session_by_id(data_manager, session_id)
        summary = get_session_summary(data_manager, session_id)
        return {
            "success": True,
            "session_id": session_id,
            "session": session,
            "summary": summary,
            "message": f"Session #{session_id} créée avec succès.",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def get_session_summary(data_manager: Any, session_id: int) -> Dict[str, Any]:
    """Récupère le résumé chiffré et financier d'une session d'inventaire."""
    try:
        return data_manager.inventory_counts.get_session_summary(session_id) or {}
    except Exception:
        return {}


def get_session_lines(
    data_manager: Any,
    session_id: int,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Récupère les lignes d'audit d'une session avec filtrage par statut ou recherche."""
    try:
        lines = data_manager.inventory_counts.get_session_lines(session_id, status=status, search=search)
        return [clean_line(l) or l for l in lines]
    except Exception:
        return []


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


def bulk_scan_session(
    data_manager: Any,
    session_id: int,
    scans: List[Dict[str, Any]],
    user_id: Optional[int] = None,
    replace_counted: bool = False,
) -> Dict[str, Any]:
    """Traite un lot de scans groupés (synchronisation hors-ligne)."""
    results = []
    success_count = 0
    error_count = 0

    for item in scans:
        barcode = str(item.get("barcode") or "").strip()
        qty = float(item.get("qty", 1) or 1)
        item_replace = item.get("replace_counted", replace_counted)
        if not barcode:
            continue
        res = scan_session_barcode(
            data_manager, session_id, barcode, qty, user_id, replace_counted=item_replace
        )
        if res.get("success"):
            success_count += 1
        else:
            error_count += 1
        results.append(res)

    summary = get_session_summary(data_manager, session_id)
    return {
        "success": True,
        "total_processed": len(results),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
        "summary": summary,
    }


def update_session_line_quantity(
    data_manager: Any,
    session_id: int,
    line_id: int,
    counted_qty: float,
) -> Dict[str, Any]:
    """Met à jour manuellement la quantité comptée d'une ligne d'inventaire."""
    try:
        result = data_manager.inventory_counts.set_counted_quantity(line_id, counted_qty)
        if isinstance(result, dict):
            if "line" in result:
                result["line"] = clean_line(result["line"])
            return result
        if result:
            return {"success": True, "message": "Quantité mise à jour avec succès."}
        return {"success": False, "message": "Impossible de modifier la quantité."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def mark_session_review(data_manager: Any, session_id: int) -> Dict[str, Any]:
    """Marque la session comme terminée / envoyée en revue."""
    try:
        ok = data_manager.inventory_counts.mark_review(session_id)
        if ok:
            return {"success": True, "message": f"Session #{session_id} envoyée en revue."}
        return {"success": False, "message": "Impossible de passer la session en revue."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def apply_session(
    data_manager: Any,
    session_id: int,
    user_id: Optional[int] = None,
    allow_unknown: bool = False,
    uncounted_action: str = "ignore",
) -> Dict[str, Any]:
    """Applique les ajustements d'inventaire sur le stock réel."""
    try:
        result = data_manager.inventory_counts.apply_session(
            session_id=session_id,
            user_id=user_id,
            allow_unknown=allow_unknown,
            uncounted_action=uncounted_action,
        )
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


def cancel_session(data_manager: Any, session_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Annule une session d'inventaire sans appliquer les écarts."""
    try:
        return data_manager.inventory_counts.cancel_session(session_id, user_id=user_id)
    except Exception as e:
        return {"success": False, "message": str(e)}


def delete_session(data_manager: Any, session_id: int) -> Dict[str, Any]:
    """Supprime complètement une session d'inventaire."""
    try:
        ok = data_manager.inventory_counts.delete_session(session_id)
        if ok:
            return {"success": True, "message": f"Session #{session_id} supprimée avec succès."}
        return {"success": False, "message": "Échec de suppression de la session."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_inventory_scopes(data_manager: Any) -> Dict[str, Any]:
    """Récupère les options de périmètre pour la création de session d'inventaire."""
    locations = []
    families = []
    try:
        if hasattr(data_manager, "locations"):
            locations = data_manager.locations.get_all_locations_flat()
    except Exception:
        pass

    try:
        if hasattr(data_manager, "families"):
            families = data_manager.families.get_all_families()
        elif hasattr(data_manager, "products") and hasattr(data_manager.products, "get_all_families"):
            families = data_manager.products.get_all_families()
    except Exception:
        pass

    return {
        "success": True,
        "scopes": {
            "locations": locations,
            "families": families,
        },
    }
