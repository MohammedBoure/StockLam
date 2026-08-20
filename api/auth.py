# api/auth.py
"""Authentication and authorization utilities for StockLam API."""

import os
from typing import Mapping

# Clé API standard pour les applications mobiles StockLam
FIXED_API_TOKEN = os.getenv("STOCKLAM_API_TOKEN", "StockLam-Inventaire-Mobile-2026")


def is_request_authorized(headers: Mapping[str, str], token: str = FIXED_API_TOKEN) -> bool:
    """Vérifie si la requête HTTP contient un jeton API valide.
    
    Prend en charge l'en-tête 'X-API-Key' ainsi que 'Authorization: Bearer <token>'.
    """
    if not token:
        return True

    api_key = headers.get("X-API-Key")
    if api_key and api_key.strip() == token:
        return True

    auth_header = headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:].strip()
        if bearer_token == token:
            return True

    return False
