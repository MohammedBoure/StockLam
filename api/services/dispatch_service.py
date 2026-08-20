# api/services/dispatch_service.py
"""Safe dispatch service for stock consumption, location transfers, and bulk operations with FEFO guarantees."""

import logging
from typing import Any, Dict, List, Optional
from .fefo_service import evaluate_fefo_compliance, sort_batches_by_fefo


def safe_consume(
    data_manager: Any,
    batch_id: int,
    qty: int = 1,
    user_id: Optional[int] = None,
    allow_fefo_override: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Exécute une consommation directe sécurisée avec contrôle FEFO strict et traçabilité utilisateur.
    
    Si un lot plus ancien existe pour le même produit et que 'allow_fefo_override' est False,
    l'opération est bloquée avec une alerte FEFO détaillée pour validation de l'opérateur.
    """
    if qty <= 0:
        return {"success": False, "message": "La quantité à consommer doit être supérieure à zéro."}

    try:
        all_batches = data_manager.batches.get_all_batches_with_details(include_zero_stock=True)
    except Exception as e:
        return {"success": False, "message": f"Erreur de lecture de l'inventaire: {e}"}

    # Rechercher le lot cible
    current_batch = next((b for b in all_batches if b.get("Batch_ID") == batch_id), None)
    if not current_batch:
        return {"success": False, "message": f"Lot ID {batch_id} introuvable."}

    current_qty = float(current_batch.get("Quantity_Current") or 0)
    if current_qty < qty:
        return {
            "success": False,
            "message": f"Quantité insuffisante en stock ({int(current_qty)} disponible(s), {qty} demandée(s)).",
            "available_qty": current_qty,
        }

    # Vérification FEFO
    product_id = current_batch.get("Product_ID")
    all_product_batches = [
        b for b in all_batches 
        if str(b.get("Product_ID")) == str(product_id) and float(b.get("Quantity_Current") or 0) > 0
    ]

    is_compliant, recommended_batch, is_violation = evaluate_fefo_compliance(
        all_product_batches, current_batch
    )

    if is_violation and not allow_fefo_override:
        rec_lot = recommended_batch.get("Lot_Number") if recommended_batch else "Inconnu"
        rec_exp = str(recommended_batch.get("Expiry_Date") or "")[:10] if recommended_batch else "-"
        curr_lot = current_batch.get("Lot_Number") or "Inconnu"
        curr_exp = str(current_batch.get("Expiry_Date") or "")[:10]

        sorted_list = sort_batches_by_fefo(all_product_batches)
        formatted_list = [
            {
                "Batch_ID": b.get("Batch_ID"),
                "Lot_Number": b.get("Lot_Number"),
                "Expiry_Date": str(b.get("Expiry_Date") or "")[:10],
                "Quantity_Current": float(b.get("Quantity_Current") or 0),
                "Location_Name": b.get("Location_Name", "---"),
                "is_recommended": (b.get("Batch_ID") == (recommended_batch.get("Batch_ID") if recommended_batch else None)),
            }
            for b in sorted_list
        ]

        return {
            "success": False,
            "fefo_violation": True,
            "message": (
                f"Alerte FEFO : Le lot '{rec_lot}' expire plus tôt ({rec_exp}) que le lot sélectionné '{curr_lot}' ({curr_exp}). "
                "Veuillez consommer le lot recommandé ou confirmer l'outrepassation FEFO (allow_fefo_override=True)."
            ),
            "scanned_batch": {
                "Batch_ID": current_batch.get("Batch_ID"),
                "Lot_Number": current_batch.get("Lot_Number"),
                "Expiry_Date": curr_exp,
                "Quantity_Current": current_qty,
                "Location_Name": current_batch.get("Location_Name", "---"),
            },
            "recommended_batch": {
                "Batch_ID": recommended_batch.get("Batch_ID") if recommended_batch else None,
                "Lot_Number": rec_lot,
                "Expiry_Date": rec_exp,
                "Quantity_Current": float(recommended_batch.get("Quantity_Current") or 0) if recommended_batch else 0,
                "Location_Name": recommended_batch.get("Location_Name", "---") if recommended_batch else "---",
            },
            "available_batches": formatted_list,
        }

    # Exécution de la transaction de consommation directe
    try:
        success = data_manager.batches.direct_consume_batch_unit(
            batch_id=batch_id,
            qty=qty,
            user_id=user_id,
            notes=notes,
        )
        if not success:
            return {"success": False, "message": "Échec de l'enregistrement de la consommation en base de données."}

        remaining = max(0.0, current_qty - qty)
        return {
            "success": True,
            "fefo_override_used": is_violation,
            "message": "Consommation enregistrée avec succès.",
            "batch_id": batch_id,
            "product_name": current_batch.get("Product_Name"),
            "lot_number": current_batch.get("Lot_Number"),
            "qty_consumed": qty,
            "remaining_qty": remaining,
        }
    except Exception as exc:
        logging.exception("Erreur lors de la consommation directe sécurisée")
        return {"success": False, "message": f"Erreur système: {exc}"}


def safe_transfer(
    data_manager: Any,
    batch_id: int,
    target_location_id: int,
    qty: int = 1,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Exécute un transfert sécurisé d'un lot vers un nouvel emplacement avec traçabilité utilisateur."""
    if qty <= 0:
        return {"success": False, "message": "La quantité à transférer doit être supérieure à zéro."}

    try:
        all_batches = data_manager.batches.get_all_batches_with_details(include_zero_stock=True)
    except Exception as e:
        return {"success": False, "message": f"Erreur de lecture de l'inventaire: {e}"}

    current_batch = next((b for b in all_batches if b.get("Batch_ID") == batch_id), None)
    if not current_batch:
        return {"success": False, "message": f"Lot ID {batch_id} introuvable."}

    current_qty = float(current_batch.get("Quantity_Current") or 0)
    if current_qty < qty:
        return {
            "success": False,
            "message": f"Quantité disponible insuffisante ({int(current_qty)} disponible(s), {qty} demandée(s)).",
            "available_qty": current_qty,
        }

    # Vérification de l'emplacement cible
    try:
        target_loc = data_manager.locations.get_location_by_id(target_location_id)
        if not target_loc:
            return {"success": False, "message": f"Emplacement de destination ID {target_location_id} introuvable."}
    except Exception as e:
        return {"success": False, "message": f"Erreur de validation de l'emplacement: {e}"}

    source_location_id = current_batch.get("Location_ID")
    if source_location_id == target_location_id:
        return {
            "success": False,
            "message": "L'emplacement de destination doit être différent de l'emplacement source.",
        }

    # Exécution du transfert en base de données
    try:
        success = data_manager.batches.transfer_batch_location(
            batch_id=batch_id,
            new_location_id=target_location_id,
            qty=qty,
            user_id=user_id,
        )
        if not success:
            return {"success": False, "message": "Échec du transfert en base de données."}

        return {
            "success": True,
            "message": "Transfert d'emplacement effectué avec succès.",
            "batch_id": batch_id,
            "product_name": current_batch.get("Product_Name"),
            "lot_number": current_batch.get("Lot_Number"),
            "qty_transferred": qty,
            "source_location_name": current_batch.get("Location_Name", "---"),
            "target_location_id": target_location_id,
            "target_location_name": target_loc.get("Location_Name", "---"),
        }
    except Exception as exc:
        logging.exception("Erreur lors du transfert d'emplacement")
        return {"success": False, "message": f"Erreur système: {exc}"}


def bulk_dispatch(
    data_manager: Any,
    mode: str,
    items: List[Dict[str, Any]],
    user_id: Optional[int] = None,
    allow_fefo_override: bool = False,
) -> Dict[str, Any]:
    """Exécute une saisie rapide multi-produits (sortie groupée ou transfert groupé)

    Chaque opération enregistre l'événement et le User_ID dans Stock_Movement_Logs.
    """
    if not items:
        return {"success": False, "message": "Aucun produit dans la liste à traiter."}

    action_mode = (mode or "consume").lower()
    success_count = 0
    failed_count = 0
    results = []

    for item in items:
        batch_id = item.get("batch_id")
        qty = int(item.get("qty", 1) or 1)
        notes = item.get("notes")
        item_override = item.get("allow_fefo_override", allow_fefo_override)

        if not batch_id:
            failed_count += 1
            results.append({"batch_id": None, "success": False, "message": "ID de lot manquant."})
            continue

        if action_mode == "consume":
            res = safe_consume(
                data_manager=data_manager,
                batch_id=batch_id,
                qty=qty,
                user_id=user_id,
                allow_fefo_override=item_override,
                notes=notes,
            )
        elif action_mode == "transfer":
            target_location_id = item.get("target_location_id")
            if not target_location_id:
                failed_count += 1
                results.append({"batch_id": batch_id, "success": False, "message": "Emplacement de destination manquant."})
                continue
            res = safe_transfer(
                data_manager=data_manager,
                batch_id=batch_id,
                target_location_id=int(target_location_id),
                qty=qty,
                user_id=user_id,
            )
        else:
            failed_count += 1
            results.append({"batch_id": batch_id, "success": False, "message": f"Mode inconnu: {action_mode}"})
            continue

        results.append(res)
        if res.get("success"):
            success_count += 1
        else:
            failed_count += 1

    all_succeeded = (failed_count == 0 and success_count > 0)
    return {
        "success": all_succeeded,
        "mode": action_mode,
        "total_items": len(items),
        "success_count": success_count,
        "failed_count": failed_count,
        "message": f"{success_count}/{len(items)} opération(s) traitée(s) avec succès.",
        "results": results,
    }
