# StockLam Inventaire Mobile

Android companion app for physical inventory count sessions in StockLam.

The app connects to the LAN API from `tools/inventory_mobile_api.py`, lists open `Counting` sessions, scans barcodes with the phone camera, and writes the physical quantity into the same session used by the desktop application.

## Daily use

1. On the main PC, open or create an Inventaire session in StockLam.
2. Start the API:

   ```powershell
   $env:INVENTORY_MOBILE_API_TOKEN = "change-this-token"
   venv\Scripts\python.exe tools\inventory_mobile_api.py --host 0.0.0.0 --port 8787
   ```

3. Install/run this Flutter app on an Android phone connected to the same LAN.
4. Set the server URL to `http://MAIN_PC_IP:8787` and enter the same token.
5. Load sessions, choose the open session, scan, enter quantity, save.

## Development

```powershell
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```
