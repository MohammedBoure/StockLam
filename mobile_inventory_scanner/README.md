# ModernStock mobile barcode scanner

The Android companion connects to a running ModernStock desktop application on the same Wi-Fi/LAN and sends barcode scans to the active desktop input field.

## Desktop host

Open the ModernStock desktop application normally. After login it starts:

- HTTP API on TCP port `8787`;
- device discovery on UDP port `8788`;
- the desktop barcode bridge.

If Windows Firewall blocks the phone, allow private-network inbound TCP `8787` and UDP `8788`.

## Phone workflow

1. Install the release APK on the Android phone.
2. Connect the phone and computer to the same Wi-Fi/LAN.
3. Tap **Rechercher les ordinateurs ModernStock**.
4. Select the computer and wait for the connected status.
5. In ModernStock, place the cursor in the barcode input field.
6. Open the camera and scan. The code is sent and submitted on the computer.
7. The camera starts on the rear camera. Use the cameraswitch button to switch between rear and front cameras.

Manual fallback: enter `http://MAIN_PC_IP:8787` and connect.

## Development and build

```powershell
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

Release APK:

```text
build\app\outputs\flutter-apk\app-release.apk
```
