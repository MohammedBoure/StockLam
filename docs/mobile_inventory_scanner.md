# ModernStock mobile barcode bridge

The Android app is a remote barcode camera for the ModernStock desktop application. It discovers ModernStock computers on the same private LAN, lets the user select one, and sends each scanned barcode to the visible desktop input field.

## Desktop host

When `main.py` finishes login, the desktop application starts automatically:

- HTTP API: TCP `8787`;
- LAN discovery: UDP `8788`;
- desktop barcode bridge: writes into the focused barcode/text field and submits it.

The standalone `tools/inventory_mobile_api.py` script still supports the legacy inventory API, but direct barcode typing requires the ModernStock desktop process because the Qt bridge lives in `main.py`.

Allow private-network inbound TCP `8787` and UDP `8788` in Windows Firewall if discovery or connection fails.

## Phone workflow

1. Install `mobile_inventory_scanner/build/app/outputs/flutter-apk/app-release.apk`.
2. Connect the phone and computer to the same Wi-Fi/LAN.
3. Tap **Rechercher les ordinateurs ModernStock**.
4. Select the target computer and wait for the connected status.
5. Place the cursor in the barcode field inside ModernStock.
6. Open the camera and scan. The barcode is sent and submitted on the computer.
7. The scanner starts with `CameraFacing.back`; the cameraswitch button calls `MobileScannerController.switchCamera()` to move between the rear and front cameras.

Manual fallback: enter `http://MAIN_PC_IP:8787` and connect.

## API routes used by ModernStock

- `GET /api/health` — desktop identity and remote-input capability;
- `POST /api/remote-scans` — sends `{ "barcode": "..." }` to the desktop bridge.

Discovery uses the UDP request `STOCKLAM_DISCOVER_V1` on port `8788`.
