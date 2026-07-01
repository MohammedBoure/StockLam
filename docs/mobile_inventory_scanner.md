# StockLam mobile inventory scanner

This adds a phone companion for the existing Inventaire session workflow.

## Architecture

- The desktop app keeps creating and reviewing inventory count sessions.
- The main PC runs `tools/inventory_mobile_api.py` on the LAN.
- The Flutter app connects to that API and records scans using the same `InventoryCountManager.scan_barcode(..., replace_counted=True)` logic used by the PySide scan dialog.
- The phone never receives MySQL credentials.

## Start the API on the main PC

```powershell
$env:INVENTORY_MOBILE_API_TOKEN = "change-this-token"
venv\Scripts\python.exe tools\inventory_mobile_api.py --host 0.0.0.0 --port 8787
```

Open Windows Firewall for port `8787` on the private network if the phone cannot connect.

Health check from another device:

```text
http://MAIN_PC_IP:8787/api/health
```

## Run the Flutter app

```powershell
cd mobile_inventory_scanner
flutter pub get
flutter run
```

In the app, set:

- Server API: `http://MAIN_PC_IP:8787`
- Token: the value of `INVENTORY_MOBILE_API_TOKEN`

## Workflow

1. Open StockLam on the PC.
2. Create or select an Inventaire session and keep it in `Counting` status.
3. Start the API on the main PC.
4. Open the Flutter app on a phone connected to the same LAN.
5. Load sessions, select the session, scan barcode, enter physical quantity, save.
6. The desktop session can refresh and review/apply the same counts.
