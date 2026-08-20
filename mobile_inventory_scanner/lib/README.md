# Mobile Inventory Scanner - Lib (`lib`)

Code source Flutter pour l'application mobile compagne MODERNSTOCK / StockLam.

## Fichiers et Structure

- **`main.dart`** : Point d'entrée de l'application, gestion de la barre de navigation inférieure (Stock Direct, Saisie Rapide, Pont Bureau), écoute UDP, sélection du poste serveur et gestion multi-comptes.
- **`api_client.dart`** : Client HTTP communiquant avec l'API StockLam (`/api/health`, `/api/auth/login`, `/api/users/list`, `/api/barcode/lookup`, `/api/stock/consume`, `/api/stock/transfer`, `/api/stock/bulk-dispatch`, `/api/locations`, `/api/remote-scans`).
- **`models.dart`** : Modèles de données typés (`DesktopDevice`, `ScanEntry`, `AuthUser`, `SavedAccount`, `ProductDetails`, `BatchDetails`, `LocationItem`, `FefoViolationData`, `BulkDispatchItem`).
- **`views/`** : Dossier des vues graphiques et composants modulaires (`auth_dialog.dart`, `direct_inventory_view.dart`, `fast_dispatch_view.dart`, `remote_scanner_view.dart`, `scanner_camera_widget.dart`).
