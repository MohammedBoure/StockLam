# api/services/barcode_service.py
"""Barcode resolution service for products and inventory batches."""

from typing import Any, Dict, List, Optional
from .fefo_service import parse_date_safe, sort_batches_by_fefo


def clean_barcode(barcode: str) -> str:
    """Nettoie le code-barres pour une recherche insensible aux tirets et espaces."""
    return str(barcode or "").strip().lower().replace("-", "").replace(" ", "")


def resolve_barcode(data_manager: Any, raw_barcode: str) -> Dict[str, Any]:
    """Recherche un produit ou lot à partir d'un code-barres scanné (Interne ou Fabricant).
    
    Retourne la fiche produit, les lots disponibles en stock et les recommandations FEFO.
    """
    barcode = str(raw_barcode or "").strip()
    if not barcode:
        return {"success": False, "found": False, "message": "Code-barres vide."}

    search_clean = clean_barcode(barcode)

    try:
        all_batches = data_manager.batches.get_all_batches_with_details(include_zero_stock=False)
    except Exception as e:
        return {"success": False, "found": False, "message": f"Erreur de lecture du stock: {e}"}

    matched_batches = []
    for b in all_batches:
        int_bc = clean_barcode(b.get("Internal_Barcode", ""))
        man_bc = clean_barcode(b.get("Barcode", ""))
        if search_clean in (int_bc, man_bc):
            matched_batches.append(b)

    # Si aucun lot direct, vérifier si le produit existe au niveau du catalogue maître
    product_id = None
    product_info = None

    if matched_batches:
        product_id = matched_batches[0].get("Product_ID")
        product_info = {
            "Product_ID": product_id,
            "Product_Name": matched_batches[0].get("Product_Name"),
            "Barcode": matched_batches[0].get("Barcode"),
            "Family_Name": matched_batches[0].get("Family_Name"),
            "Manuf_Name": matched_batches[0].get("Manuf_Name"),
            "Stock_Unit": matched_batches[0].get("Stock_Unit", "Boîte"),
            "Minimum_Stock_Level": matched_batches[0].get("Minimum_Stock_Level", 5),
        }
    else:
        # Recherche produit dans Products_Master
        try:
            prod = data_manager.products.get_product_by_barcode(barcode)
            if prod:
                product_id = prod.get("Product_ID")
                product_info = {
                    "Product_ID": product_id,
                    "Product_Name": prod.get("Product_Name"),
                    "Barcode": prod.get("Barcode"),
                    "Family_Name": prod.get("Family_Name"),
                    "Manuf_Name": prod.get("Manuf_Name"),
                    "Stock_Unit": prod.get("Stock_Unit", "Boîte"),
                    "Minimum_Stock_Level": prod.get("Minimum_Stock_Level", 5),
                }
        except Exception:
            pass

    if not product_id:
        return {
            "success": True,
            "found": False,
            "barcode": barcode,
            "message": "Aucun produit ou lot associé à ce code-barres.",
            "product": None,
            "batches": [],
        }

    # Récupérer tous les lots disponibles pour ce produit pour l'évaluation FEFO
    all_product_batches = [
        b for b in all_batches 
        if str(b.get("Product_ID")) == str(product_id) and float(b.get("Quantity_Current") or 0) > 0
    ]

    sorted_batches = sort_batches_by_fefo(all_product_batches)
    recommended_batch_id = sorted_batches[0].get("Batch_ID") if sorted_batches else None

    # Formater les lots pour la réponse API
    formatted_batches = []
    for b in sorted_batches:
        is_rec = (b.get("Batch_ID") == recommended_batch_id)
        is_scanned = any(m.get("Batch_ID") == b.get("Batch_ID") for m in matched_batches)
        formatted_batches.append({
            "Batch_ID": b.get("Batch_ID"),
            "Product_ID": b.get("Product_ID"),
            "Internal_Barcode": b.get("Internal_Barcode"),
            "Lot_Number": b.get("Lot_Number"),
            "Expiry_Date": str(b.get("Expiry_Date") or "")[:10],
            "Quantity_Current": float(b.get("Quantity_Current") or 0),
            "Location_ID": b.get("Location_ID"),
            "Location_Name": b.get("Location_Name", "Emplacement inconnu"),
            "Date_Received": str(b.get("Date_Received") or "")[:10],
            "is_recommended": is_rec,
            "is_scanned_match": is_scanned,
        })

    # Lot directement scanné (si code-barres de lot interne)
    scanned_batch_detail = None
    if matched_batches:
        scanned_batch_detail = next(
            (fb for fb in formatted_batches if fb["Batch_ID"] == matched_batches[0].get("Batch_ID")),
            None
        )

    return {
        "success": True,
        "found": True,
        "barcode": barcode,
        "product": product_info,
        "scanned_batch": scanned_batch_detail,
        "recommended_batch_id": recommended_batch_id,
        "batches": formatted_batches,
        "total_available_qty": sum(fb["Quantity_Current"] for fb in formatted_batches),
    }
