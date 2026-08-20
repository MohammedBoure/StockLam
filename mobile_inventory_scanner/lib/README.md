# Mobile Inventory Scanner - Lib (`lib`)

Code source Flutter pour l'application mobile compagne MODERNSTOCK / StockLam.

## Fichiers et Structure

- **`main.dart`** : Point d'entrée de l'application, gestion de la barre de navigation inférieure (Tabs), écoute UDP et sélection du poste serveur.
- **`api_client.dart`** : Client HTTP communiquant avec l'API StockLam (`/api/health`, `/api/barcode/lookup`, `/api/stock/consume`, `/api/stock/transfer`, `/api/locations`, `/api/remote-scans`).
- **`models.dart`** : Modèles de données typés (`DesktopDevice`, `ScanEntry`, `ProductDetails`, `BatchDetails`, `LocationItem`, `FefoViolationData`).
- **`views/`** : Dossier des vues graphiques et composants modulaires (`direct_inventory_view.dart`, `remote_scanner_view.dart`, `scanner_camera_widget.dart`).
