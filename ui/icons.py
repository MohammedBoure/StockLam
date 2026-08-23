# ui/icons.py
"""Dual-tone vector icons generator matching the modern outline & flat color aesthetic."""

from typing import Dict, Optional
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer

_icon_cache: Dict[str, QIcon] = {}

DUOTONE_SVGS: Dict[str, str] = {
    # 0: Tableau de Bord (City Skyline / Analytics with Yellow/Teal fill and dark outline)
    "dashboard": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="8" cy="8" r="4" fill="#FFB800" stroke="#2C3E50" stroke-width="2"/>
        <rect x="4" y="11" width="9" height="17" rx="1.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <rect x="15" y="6" width="13" height="22" rx="1.5" fill="#00A896" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <line x1="7" y1="16" x2="10" y2="16" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="7" y1="21" x2="10" y2="21" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="19" y1="11" x2="24" y2="11" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="19" y1="16" x2="24" y2="16" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="19" y1="21" x2="24" y2="21" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>
    </svg>''',

    # 1: Données de Base (Briefcase / Master folders with Yellow/Teal accents)
    "master_data": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="3" y="9" width="26" height="19" rx="2.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M11 9V6C11 4.9 11.9 4 13 4H19C20.1 4 21 4.9 21 6V9" fill="none" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <rect x="8" y="9" width="4" height="19" fill="#FFB800" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <rect x="20" y="9" width="4" height="19" fill="#FFB800" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <rect x="14" y="15" width="4" height="5" rx="1" fill="#FF6B6B" stroke="#2C3E50" stroke-width="1.8"/>
    </svg>''',

    # 2: Achats & Entrées (Paper Airplane with Yellow/Teal wing fill)
    "procurement": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M28 4L3 14L13 19L28 4Z" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M28 4L18 28L13 19L28 4Z" fill="#00A896" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M13 19L15 25L18 20" fill="#FFB800" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
    </svg>''',

    # 3: Stock & Magasin (Boxes / Warehouse shelves / Jigsaw puzzle)
    "inventory": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="14" width="11" height="14" rx="1.5" fill="#FFB800" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <rect x="17" y="6" width="11" height="22" rx="1.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M7 14V18H12V14" fill="#FF6B6B" stroke="#2C3E50" stroke-width="1.8"/>
        <line x1="20" y1="11" x2="25" y2="11" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="20" y1="16" x2="25" y2="16" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="20" y1="21" x2="25" y2="21" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
    </svg>''',

    # 6: Sous-Traitants (Operator Headset / Partner)
    "services": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="14" r="7" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2"/>
        <path d="M8 15C8 10 11.5 6 16 6C20.5 6 24 10 24 15" fill="none" stroke="#2C3E50" stroke-width="2.4" stroke-linecap="round"/>
        <rect x="6" y="13" width="3" height="6" rx="1.5" fill="#00A896" stroke="#2C3E50" stroke-width="2"/>
        <rect x="23" y="13" width="3" height="6" rx="1.5" fill="#00A896" stroke="#2C3E50" stroke-width="2"/>
        <path d="M24 18V21C24 22.5 22.5 24 20 24H18" fill="none" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <circle cx="17" cy="24" r="1.5" fill="#FF6B6B"/>
        <path d="M6 28C6 24.5 10.5 23 16 23C21.5 23 26 24.5 26 28" fill="none" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
    </svg>''',

    # 8: Réclamations (Speech bubble with Info badge / Alert)
    "reclamations": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M6 6H26C27.1 6 28 6.9 28 8V20C28 21.1 27.1 22 26 22H14L8 27V22H6C4.9 22 4 21.1 4 20V8C4 6.9 4.9 6 6 6Z" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <circle cx="16" cy="14" r="6" fill="#FF6B6B" stroke="#2C3E50" stroke-width="2"/>
        <line x1="16" y1="11" x2="16" y2="14.5" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
        <circle cx="16" cy="17" r="1" fill="#FFFFFF"/>
    </svg>''',

    # 9: Inventaire (Checklist Document / Award Medal / Star Badge)
    "inventaire": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="5" y="4" width="22" height="24" rx="2" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <rect x="9" y="8" width="4" height="4" rx="1" fill="#00A896" stroke="#2C3E50" stroke-width="1.8"/>
        <line x1="16" y1="10" x2="23" y2="10" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <rect x="9" y="14" width="4" height="4" rx="1" fill="#FFB800" stroke="#2C3E50" stroke-width="1.8"/>
        <line x1="16" y1="16" x2="23" y2="16" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <rect x="9" y="20" width="4" height="4" rx="1" fill="#00A896" stroke="#2C3E50" stroke-width="1.8"/>
        <line x1="16" y1="22" x2="23" y2="22" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 7: Traçabilité (Route / Map pins path - exact icon from image row 4 col 5)
    "history": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M8 12C8 9.8 9.8 8 12 8C14.2 8 16 9.8 16 12C16 15 12 19 12 19C12 19 8 15 8 12Z" fill="#FFB800" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <circle cx="12" cy="12" r="1.5" fill="#2C3E50"/>
        <path d="M18 20C18 17.8 19.8 16 22 16C24.2 16 26 17.8 26 20C26 23 22 27 22 27C22 27 18 23 18 20Z" fill="#8B5CF6" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <circle cx="22" cy="20" r="1.5" fill="#FFFFFF"/>
        <path d="M12 21C12 25 18 21 18 24" fill="none" stroke="#2C3E50" stroke-width="2" stroke-dasharray="2 3" stroke-linecap="round"/>
    </svg>''',

    # 5: Utilisateurs (Org tree with 3 users - exact icon from image row 2 col 5)
    "users": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="8" r="4.5" fill="#FFB800" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="16" cy="7" r="1.8" fill="#2C3E50"/>
        <circle cx="8" cy="22" r="4.5" fill="#6366F1" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="8" cy="21" r="1.8" fill="#FFFFFF"/>
        <circle cx="24" cy="22" r="4.5" fill="#6366F1" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="24" cy="21" r="1.8" fill="#FFFFFF"/>
        <path d="M16 13V16M16 16H8V17.5M16 16H24V17.5" fill="none" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # 4: Paramètres (Settings sliders)
    "settings": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <line x1="6" y1="9" x2="26" y2="9" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="12" cy="9" r="3.5" fill="#00A896" stroke="#2C3E50" stroke-width="2"/>
        <line x1="6" y1="16" x2="26" y2="16" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="20" cy="16" r="3.5" fill="#FFB800" stroke="#2C3E50" stroke-width="2"/>
        <line x1="6" y1="23" x2="26" y2="23" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="10" cy="23" r="3.5" fill="#64748B" stroke="#2C3E50" stroke-width="2"/>
    </svg>''',

    # Logout (Power / Exit)
    "logout": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M16 5V15" stroke="#FF6B6B" stroke-width="2.6" stroke-linecap="round"/>
        <path d="M10 9C6.5 11.2 4.5 15 4.5 19C4.5 25.4 9.6 30.5 16 30.5C22.4 30.5 27.5 25.4 27.5 19C27.5 15 25.5 11.2 22 9" fill="none" stroke="#2C3E50" stroke-width="2.6" stroke-linecap="round"/>
    </svg>''',

    # Collapse Sidebar
    "collapse": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="20" rx="3" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2"/>
        <line x1="12" y1="6" x2="12" y2="26" stroke="#2C3E50" stroke-width="2"/>
        <path d="M21 13L18 16L21 19" fill="none" stroke="#00A896" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # Expand Sidebar
    "expand": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="20" rx="3" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2"/>
        <line x1="12" y1="6" x2="12" y2="26" stroke="#2C3E50" stroke-width="2"/>
        <path d="M18 13L21 16L18 19" fill="none" stroke="#FFB800" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # Menu Hamburger Toggle
    "menu": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <line x1="6" y1="9" x2="26" y2="9" stroke="#2C3E50" stroke-width="2.5" stroke-linecap="round"/>
        <line x1="6" y1="16" x2="20" y2="16" stroke="#00A896" stroke-width="2.5" stroke-linecap="round"/>
        <line x1="6" y1="23" x2="26" y2="23" stroke="#FFB800" stroke-width="2.5" stroke-linecap="round"/>
    </svg>''',
}

def get_duotone_icon(name: str, size: int = 64) -> QIcon:
    """Returns a cached high-resolution QIcon in the dual-tone illustration theme."""
    cache_key = f"{name}_{size}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    svg_content = DUOTONE_SVGS.get(name)
    if not svg_content:
        # Fallback to empty icon
        return QIcon()

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon

def get_reclamation_icon() -> QIcon:
    """Compatibility helper for existing reclamation views."""
    return get_duotone_icon("reclamations", 32)

