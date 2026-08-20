# api/auth.py
"""Authentication and authorization utilities for StockLam API."""

import logging
import os
from typing import Any, Dict, List, Mapping, Optional

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


def authenticate_user(data_manager: Any, username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authentifie un utilisateur auprès du gestionnaire d'utilisateurs StockLam."""
    try:
        user = data_manager.users.authenticate(username, password)
        if not user:
            return None
        return {
            "user_id": user.get("User_ID"),
            "username": user.get("Username"),
            "full_name": user.get("Full_Name") or user.get("Username"),
            "role": user.get("Role", "Technician"),
            "permissions": user.get("Permissions", {}),
        }
    except Exception as exc:
        logging.error("Erreur lors de l'authentification utilisateur API: %s", exc)
        return None


def get_active_users_list(data_manager: Any) -> List[Dict[str, Any]]:
    """Récupère la liste des utilisateurs actifs pour affichage dans l'application."""
    try:
        users = data_manager.users.get_all_users()
        return [
            {
                "user_id": u.get("User_ID"),
                "username": u.get("Username"),
                "full_name": u.get("Full_Name") or u.get("Username"),
                "role": u.get("Role", "Technician"),
            }
            for u in users
            if u.get("Is_Active", 1) == 1
        ]
    except Exception:
        return []
