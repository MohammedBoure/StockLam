# tools/inventory_mobile_api.py
"""StockLam External and Mobile API CLI Entrypoint.

Exposes LAN-based REST API and UDP discovery for:
- Barcode scanning, lookup & product resolution
- Safe stock consumption with FEFO/FIFO validation (identical to ui/widgets/inventory/tabs_dispatch.py)
- Safe stock location transfer
- Storage location reference catalog
- Remote desktop barcode scanning bridge
- Mobile inventory counting sessions

Run standalone on the main PC:
    python tools/inventory_mobile_api.py --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api import (
    DISCOVERY_PORT,
    DISCOVERY_REQUEST,
    FIXED_API_TOKEN,
    InventoryDiscoveryServer,
    ReusableThreadingHTTPServer,
    StockLamApiHandler,
    StockLamApiServer,
    build_discovery_server,
    build_server,
)

# Alias pour compatibilité ascendante
InventoryMobileApi = StockLamApiHandler


def main():
    parser = argparse.ArgumentParser(description="StockLam External Mobile & Barcode API")
    parser.add_argument("--host", default=os.getenv("INVENTORY_MOBILE_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("INVENTORY_MOBILE_API_PORT", "8787")))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Initialisation du gestionnaire de données si exécuté en autonome
    from database import Database, LabDataManager

    db = Database()
    data_manager = LabDataManager(db)

    server = build_server(args.host, args.port, data_manager=data_manager)
    discovery_server = None
    discovery_thread = None

    try:
        discovery_server = build_discovery_server(
            args.host,
            int(os.getenv("INVENTORY_MOBILE_DISCOVERY_PORT", str(DISCOVERY_PORT))),
            args.port,
            device_name=server.device_name,
            device_id=server.device_id,
        )
        discovery_thread = threading.Thread(
            target=discovery_server.serve_forever,
            name="InventoryMobileDiscovery",
            daemon=True,
        )
        discovery_thread.start()
        logging.info("StockLam UDP Discovery listening on port %s", discovery_server.port)
    except OSError as exc:
        logging.warning("StockLam Discovery could not be started: %s", exc)

    logging.info("StockLam API server running on http://%s:%s", args.host, args.port)
    logging.info("API Key protection enabled with token: %s", FIXED_API_TOKEN)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping StockLam API server.")
    finally:
        if discovery_server is not None:
            discovery_server.shutdown()
            discovery_server.server_close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
