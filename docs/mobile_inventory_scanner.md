# StockLam mobile inventory scanner

Ready-to-use Android companion for the current StockLam **Inventaire** workflow.

## What it does

- Uses the desktop StockLam database through a small LAN API.
- Lists open `Counting` inventory sessions.
- Scans barcodes with the phone camera.
- Shows product, lot, expiry, location, program quantity, counted quantity, and status.
- Saves the physical quantity directly into the selected StockLam inventory session.
- Uses the same backend method as the desktop scan dialog: `InventoryCountManager.scan_barcode(..., replace_counted=True)`.
- The phone never receives MySQL credentials.

## Start the API on the main PC

From the repository root:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
.\tools\start_inventory_mobile_api.ps1
```

The script prints the PC IP addresses. Use one of them in the phone app, for example:

```text
http://192.168.1.10:8787
```

If Windows Firewall blocks the phone, allow private-network inbound TCP on port `8787`.

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
5. Enter the server URL and token if configured.
6. Tap **Sessions**, select the open inventory session.
7. Scan a product barcode, verify details, enter physical quantity, tap **Enregistrer**.
8. Return to the desktop Inventaire screen, refresh/review/apply as usual.

## API endpoints

- `GET /api/health`
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
