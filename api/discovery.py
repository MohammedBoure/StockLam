# api/discovery.py
"""UDP Discovery Server for automatic detection of StockLam PC on local network."""

import json
import logging
import socket
from typing import Tuple

DISCOVERY_PORT = 8788
DISCOVERY_REQUEST = b"STOCKLAM_DISCOVER_V1"


class InventoryDiscoveryServer:
    """Répondeur UDP permettant aux téléphones de détecter automatiquement les postes StockLam sur le réseau local."""

    def __init__(self, host: str, port: int, api_port: int, device_name: str, device_id: str):
        self.host = host
        self.port = int(port)
        self.api_port = int(api_port)
        self.device_name = device_name
        self.device_id = device_id
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(1.0)
        self._running = False

    def serve_forever(self):
        self._running = True
        while self._running:
            try:
                data, address = self._socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            if data.strip() != DISCOVERY_REQUEST:
                continue

            payload = json.dumps({
                "app": "StockLam",
                "service": "inventory_mobile_api",
                "device_name": self.device_name,
                "device_id": self.device_id,
                "api_port": self.api_port,
                "version": "1.0",
            }).encode("utf-8")

            try:
                self._socket.sendto(payload, address)
            except OSError as error:
                logging.debug("Discovery response failed to %s: %s", address, error)

    def shutdown(self):
        self._running = False

    def server_close(self):
        self._socket.close()


def build_discovery_server(host: str, port: int, api_port: int, device_name: str, device_id: str) -> InventoryDiscoveryServer:
    return InventoryDiscoveryServer(host, port, api_port, device_name, device_id)
