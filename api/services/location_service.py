# api/services/location_service.py
"""Location service for querying storage locations."""

from typing import Any, Dict, List


def get_locations(data_manager: Any) -> List[Dict[str, Any]]:
    """Récupère la liste hiérarchique et à plat des emplacements de stockage."""
    try:
        raw_locations = data_manager.locations.get_all_locations_flat()
        formatted = []
        for loc in raw_locations:
            formatted.append({
                "Location_ID": loc.get("Location_ID"),
                "Location_Name": loc.get("Location_Name"),
                "Parent_ID": loc.get("Parent_ID"),
                "Type_Name": loc.get("Type_Name"),
                "Full_Path": loc.get("Location_Name"),
            })
        return formatted
    except Exception:
        # Repli si get_all_locations_flat échoue
        try:
            raw = data_manager.locations.get_all_locations()
            return [
                {
                    "Location_ID": l.get("Location_ID"),
                    "Location_Name": l.get("Location_Name"),
                    "Parent_ID": l.get("Parent_ID"),
                    "Type_Name": l.get("Type_Name"),
                    "Full_Path": l.get("Location_Name"),
                }
                for l in raw
            ]
        except Exception:
            return []
