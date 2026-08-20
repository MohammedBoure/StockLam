# MODERNSTOCK Mobile Barcode Scanner

The Android companion connects to a running MODERNSTOCK desktop application on the same Wi-Fi/LAN and sends barcode scans to the active desktop input field.

## Desktop Host

Open the MODERNSTOCK desktop application normally. After login it starts:

- HTTP API on TCP port 8787;
- device discovery on UDP port 8788;
- the desktop barcode bridge.

If Windows Firewall blocks the phone, allow private-network inbound TCP 8787 and UDP 8788.

## Phone Workflow

1. Install the release APK on the Android phone (pp-arm64-v8a-release.apk for modern devices).
2. Connect the phone and computer to the same Wi-Fi/LAN.
3. Tap **Rechercher les ordinateurs ModernStock**.
4. Select the computer and wait for the connected status.
5. In MODERNSTOCK desktop, place the cursor in the barcode input field.
6. Open the camera and scan. The code is sent and submitted on the computer.
7. The camera starts on the rear camera. Use the camera switch button to switch between rear and front cameras.

Manual fallback: enter http://MAIN_PC_IP:8787 and connect.

## Development and Build

`powershell
flutter pub get
flutter analyze
flutter test

# Standard universal release APK:
flutter build apk --release

# Ultra-lightweight ABI-split release APKs (< 25 MB each, recommended):
flutter build apk --split-per-abi --obfuscate --split-debug-info=build/symbols
`

### Generated Release APKs

- Modern 64-bit phones (99% of Android phones): uild/app/outputs/flutter-apk/app-arm64-v8a-release.apk
- 32-bit legacy devices: uild/app/outputs/flutter-apk/app-armeabi-v7a-release.apk
- 64-bit emulators: uild/app/outputs/flutter-apk/app-x86_64-release.apk
- Universal fallback APK: uild/app/outputs/flutter-apk/app-release.apk
