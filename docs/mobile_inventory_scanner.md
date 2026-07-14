# StockLam mobile inventory scanner

Ready-to-use Android companion for the current StockLam **Inventaire** workflow.

## What it does

- Uses the desktop StockLam database through a small LAN API.
- Discovers running StockLam computers automatically on the same Wi-Fi/LAN.
- Connects to a selected computer and sends camera scans to the active StockLam input field.
- Lists open `Counting` inventory sessions.
- Scans barcodes with the phone camera.
- Shows product, lot, expiry, location, program quantity, counted quantity, and status.
- Saves the physical quantity directly into the selected StockLam inventory session.
- Uses the same backend method as the desktop scan dialog: `InventoryCountManager.scan_barcode(..., replace_counted=True)`.
- The phone never receives MySQL credentials.

## Start the desktop host

Open StockLam normally with `main.py`. After login, it automatically starts:

- the HTTP API on TCP port `8787`;
- LAN discovery on UDP port `8788`;
- the desktop barcode bridge used by **Vers ordinateur** mode.

The standalone API script remains available for inventory-only use, but direct typing into StockLam requires the desktop application to be open.

If automatic discovery is blocked, enter the computer address manually, for example:

```text
http://192.168.1.10:8787
```

If Windows Firewall blocks the phone, allow private-network inbound TCP `8787` and UDP `8788`.

## Build or run the Android app

```powershell
cd mobile_inventory_scanner
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Debug APK output:

```text
mobile_inventory_scanner\build\app\outputs\flutter-apk\app-debug.apk
```

## Practical workflow

1. Open StockLam on the PC.
2. Create or select an Inventaire session and keep it in `Counting` status.
3. Start the API on the main PC with `tools\start_inventory_mobile_api.ps1`.
4. Install/run the Android app on a phone connected to the same Wi-Fi/LAN.
5. Tap **Rechercher les ordinateurs StockLam** and choose the target PC.
6. In **Vers ordinateur** mode, place the cursor in a StockLam barcode/text field and scan with the phone camera; the code is written and submitted on the PC.
7. In **Inventaire** mode, select an open session, scan a product, verify details, enter the physical quantity, then tap **Enregistrer**.
8. Return to the desktop Inventaire screen and refresh/review/apply as usual.

## API endpoints

- `GET /api/health`
- `POST /api/remote-scans`
- `GET /api/inventory-sessions?status=Counting`
- `GET /api/inventory-sessions/{session_id}/lookup?barcode=...`
- `POST /api/inventory-sessions/{session_id}/scan`

`POST /scan` body:

```json
{
  "barcode": "123456",
  "qty": 5,
  "replace_counted": true
}
```
