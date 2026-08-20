# api/services/fefo_service.py
"""FEFO (First Expired First Out) & FIFO validation and recommendation engine."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple


def parse_date_safe(date_val: Any) -> Optional[date]:
    """Conversion robuste de formats de date en objet date Python."""
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        clean = date_val.split(" ")[0].strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(clean, fmt).date()
            except ValueError:
                continue
    return None


def sort_batches_by_fefo(batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trie les lots selon le principe FEFO (puis FIFO en cas d'égalité).
    
    1. Date de péremption la plus proche (FEFO).
    2. Date de réception/création la plus ancienne (FIFO).
    """
    def _sort_key(batch: Dict[str, Any]):
        exp = parse_date_safe(batch.get("Expiry_Date")) or date.max
        rcv = batch.get("Date_Received") or batch.get("Created_At") or ""
        rcv_str = str(rcv) if rcv else "9999"
        return (exp, rcv_str)

    return sorted(batches, key=_sort_key)


def evaluate_fefo_compliance(
    all_product_batches: List[Dict[str, Any]], 
    current_batch: Dict[str, Any]
) -> Tuple[bool, Optional[Dict[str, Any]], bool]:
    """Évalue la conformité FEFO du lot scanné.
    
    Retourne : (is_compliant, recommended_batch, is_violation)
    - is_compliant: True si le lot est le lot recommandé ou conforme
    - recommended_batch: Le lot prioritaire à consommer selon FEFO
    - is_violation: True si un lot plus ancien existe et qu'il y a violation de FEFO/FIFO
    """
    if not all_product_batches:
        return True, current_batch, False

    # Filtrer uniquement les lots avec stock positif
    available_batches = [
        b for b in all_product_batches 
        if float(b.get("Quantity_Current") or 0) > 0
    ]

    if not available_batches:
        return True, current_batch, False

    sorted_batches = sort_batches_by_fefo(available_batches)
    recommended_batch = sorted_batches[0]

    # Si le lot scanné est le lot recommandé
    if str(current_batch.get("Batch_ID")) == str(recommended_batch.get("Batch_ID")):
        return True, recommended_batch, False

    curr_exp = parse_date_safe(current_batch.get("Expiry_Date"))
    rec_exp = parse_date_safe(recommended_batch.get("Expiry_Date"))

    # Si le lot scanné n'a pas de date d'expiration
    if not curr_exp:
        return True, current_batch, False

    is_violation = False

    # 1. Violation FEFO : le lot recommandé expire avant le lot actuel
    if rec_exp and rec_exp < curr_exp:
        is_violation = True
    # 2. Violation FIFO : mêmes dates d'expiration, mais le lot recommandé est entré en premier
    elif rec_exp == curr_exp:
        curr_rcv = str(current_batch.get("Date_Received") or current_batch.get("Created_At") or "9999")
        rec_rcv = str(recommended_batch.get("Date_Received") or recommended_batch.get("Created_At") or "9999")
        if rec_rcv < curr_rcv:
            is_violation = True

    return not is_violation, recommended_batch, is_violation
