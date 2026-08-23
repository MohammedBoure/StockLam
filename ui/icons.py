# ui/icons.py
"""Dual-tone vector icons generator matching the modern outline & flat color aesthetic."""

from typing import Dict, Optional
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer

_icon_cache: Dict[str, QIcon] = {}

DUOTONE_SVGS: Dict[str, str] = {
    # 0: Tableau de Bord (Analytics Board with rising KPI trends, Blue & Gold bars)
    "dashboard": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="3" y="4" width="26" height="24" rx="3" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <rect x="6.5" y="16" width="4.5" height="9" rx="1" fill="#0284C7" stroke="#2C3E50" stroke-width="1.8"/>
        <rect x="13.5" y="11" width="4.5" height="14" rx="1" fill="#00A896" stroke="#2C3E50" stroke-width="1.8"/>
        <rect x="20.5" y="7" width="4.5" height="18" rx="1" fill="#FFB800" stroke="#2C3E50" stroke-width="1.8"/>
        <path d="M7 13L14 8L23 5" fill="none" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="23" cy="5" r="2" fill="#FF6B6B"/>
    </svg>''',

    # 1: Données de Base (Master Database layers & registry catalog)
    "master_data": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <ellipse cx="16" cy="8" rx="11" ry="4.5" fill="#FFB800" stroke="#2C3E50" stroke-width="2.2"/>
        <path d="M5 8V16C5 18.5 9.9 20.5 16 20.5C22.1 20.5 27 18.5 27 16V8" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2"/>
        <path d="M5 16V24C5 26.5 9.9 28.5 16 28.5C22.1 28.5 27 26.5 27 24V16" fill="#00A896" stroke="#2C3E50" stroke-width="2.2"/>
        <line x1="9" y1="14" x2="13" y2="14" stroke="#2C3E50" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="9" y1="22" x2="13" y2="22" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>
    </svg>''',

    # 2: Achats & Entrées (Procurement / Shopping cart with incoming goods & reception receipt)
    "procurement": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="11" cy="27" r="2.5" fill="#2C3E50"/>
        <circle cx="23" cy="27" r="2.5" fill="#2C3E50"/>
        <path d="M4 5H7.5L10.5 20H25L28 9H8.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <rect x="12" y="7" width="11" height="9" rx="1.5" fill="#10B981" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <path d="M12 11H23" stroke="#2C3E50" stroke-width="1.8"/>
        <path d="M17.5 7V16" stroke="#FFB800" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 3: Stock & Magasin (Warehouse storage racks holding inventory products on shelves)
    "inventory": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <line x1="5" y1="4" x2="5" y2="28" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="27" y1="4" x2="27" y2="28" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="5" y1="16" x2="27" y2="16" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="5" y1="28" x2="27" y2="28" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round"/>
        <rect x="8" y="8" width="7" height="7" rx="1" fill="#00A896" stroke="#2C3E50" stroke-width="1.8" stroke-linejoin="round"/>
        <line x1="11.5" y1="8" x2="11.5" y2="15" stroke="#FFFFFF" stroke-width="1.4"/>
        <rect x="17" y="9" width="7" height="6" rx="1" fill="#FFB800" stroke="#2C3E50" stroke-width="1.8" stroke-linejoin="round"/>
        <rect x="8" y="19" width="9" height="8" rx="1" fill="#FF6B6B" stroke="#2C3E50" stroke-width="1.8" stroke-linejoin="round"/>
        <line x1="12.5" y1="19" x2="12.5" y2="27" stroke="#2C3E50" stroke-width="1.4"/>
        <rect x="19" y="20" width="6" height="7" rx="1" fill="#F8FAFC" stroke="#2C3E50" stroke-width="1.8" stroke-linejoin="round"/>
    </svg>''',

    # 6: Sous-Traitants (Trading Partners Handshake & Deal exchange)
    "services": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M3 17L8 12L13 16L9 21L3 17Z" fill="#00A896" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M29 17L24 12L19 16L23 21L29 17Z" fill="#FFB800" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M12 15L15 12C15.8 11.2 17.2 11.2 18 12L20 14L15 19L11 16" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <path d="M15 19L17 21C17.8 21.8 19.2 21.8 20 21L21 20" fill="none" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <circle cx="16" cy="6" r="3" fill="#FF6B6B" stroke="#2C3E50" stroke-width="1.8"/>
        <path d="M15 6H17M16 5V7" stroke="#FFFFFF" stroke-width="1.4" stroke-linecap="round"/>
    </svg>''',

    # 8: Réclamations (Non-conformity Claim Warning & Alert)
    "reclamations": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M16 3L28 26C28.5 27 27.8 28.5 26.5 28.5H5.5C4.2 28.5 3.5 27 4 26L16 3Z" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M16 7L25 25H7L16 7Z" fill="#FF6B6B" stroke="#2C3E50" stroke-width="1.8" stroke-linejoin="round"/>
        <line x1="16" y1="12" x2="16" y2="19" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round"/>
        <circle cx="16" cy="22.5" r="1.3" fill="#FFFFFF"/>
    </svg>''',

    # 9: Inventaire (Physical Count Checklist & Barcode audit scanner)
    "inventaire": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="5" y="5" width="22" height="24" rx="2.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M12 5V3.5C12 2.7 12.7 2 13.5 2H18.5C19.3 2 20 2.7 20 3.5V5" fill="#FFB800" stroke="#2C3E50" stroke-width="2" stroke-linejoin="round"/>
        <path d="M8.5 10L10.5 12L14.5 8" fill="none" stroke="#007572" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="17" y1="10" x2="23" y2="10" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <path d="M8.5 16L10.5 18L14.5 14" fill="none" stroke="#007572" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="17" y1="16" x2="23" y2="16" stroke="#2C3E50" stroke-width="2" stroke-linecap="round"/>
        <rect x="8" y="21" width="16" height="5" rx="1" fill="#E8F8F5" stroke="#007572" stroke-width="1.5"/>
        <line x1="11" y1="22.5" x2="11" y2="24.5" stroke="#007572" stroke-width="1.5"/>
        <line x1="14" y1="22.5" x2="14" y2="24.5" stroke="#007572" stroke-width="1.5"/>
        <line x1="17" y1="22.5" x2="17" y2="24.5" stroke="#007572" stroke-width="1.5"/>
        <line x1="20" y1="22.5" x2="20" y2="24.5" stroke="#007572" stroke-width="1.5"/>
    </svg>''',

    # 7: Traçabilité (Internal stock movement audit trail, transfer flow & chronological history)
    "history": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="16" r="11.5" fill="#F8FAFC" stroke="#2C3E50" stroke-width="2.2"/>
        <path d="M16 4.5A11.5 11.5 0 0 1 27.5 16" fill="none" stroke="#8B5CF6" stroke-width="2.6" stroke-linecap="round"/>
        <polygon points="27.5,12 27.5,17 22.5,17" fill="#8B5CF6" stroke="#2C3E50" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="16" cy="16" r="2.5" fill="#FFB800" stroke="#2C3E50" stroke-width="1.8"/>
        <path d="M16 9V16L20 18" fill="none" stroke="#2C3E50" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M6 25L10 21L14 25" fill="none" stroke="#00A896" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # 5: Utilisateurs (Org hierarchy network tree of team users)
    "users": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="8" r="4.5" fill="#FFB800" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="16" cy="7" r="1.8" fill="#2C3E50"/>
        <circle cx="8" cy="22" r="4.5" fill="#6366F1" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="8" cy="21" r="1.8" fill="#FFFFFF"/>
        <circle cx="24" cy="22" r="4.5" fill="#6366F1" stroke="#2C3E50" stroke-width="2"/>
        <circle cx="24" cy="21" r="1.8" fill="#FFFFFF"/>
        <path d="M16 13V16M16 16H8V17.5M16 16H24V17.5" fill="none" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # 4: Paramètres (Settings sliders & Configuration)
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

