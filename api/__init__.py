# api/__init__.py
"""StockLam External API Package for Mobile and Barcode Scanner Clients.

Provides LAN-based REST API and UDP discovery for:
- Barcode lookup & product resolution
- Safe stock consumption with FEFO/FIFO validation
- Safe stock location transfer
- Location reference data
- Remote desktop barcode scanning bridge
- Mobile inventory counting sessions
"""

from .auth import FIXED_API_TOKEN, is_request_authorized
from .discovery import (
    DISCOVERY_PORT,
    DISCOVERY_REQUEST,
    InventoryDiscoveryServer,
    build_discovery_server,
)
from .server import (
    ReusableThreadingHTTPServer,
    StockLamApiHandler,
    StockLamApiServer,
    build_server,
)

__all__ = [
    "FIXED_API_TOKEN",
    "DISCOVERY_PORT",
    "DISCOVERY_REQUEST",
    "InventoryDiscoveryServer",
    "ReusableThreadingHTTPServer",
    "StockLamApiHandler",
    "StockLamApiServer",
    "build_discovery_server",
    "build_server",
    "is_request_authorized",
]
