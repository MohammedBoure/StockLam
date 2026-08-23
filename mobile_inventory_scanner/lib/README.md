# Mobile Inventory Scanner - Lib (`lib`)

Code source Flutter pour l'application mobile compagne MODERNSTOCK / StockLam.

## Fichiers et Structure

- **`main.dart`** : Point d'entrée de l'application, gestion de la barre de navigation inférieure (Stock Direct, Saisie Rapide, Inventaire Physique, Pont Bureau), écoute UDP, sélection du poste serveur et gestion multi-comptes.
- **`api_client.dart`** : Client HTTP communiquant avec l'ensemble de l'API StockLam (santé, authentification, dispatch, transferts, découverte des scopes et cycle de vie complet des sessions d'inventaire).
- **`models.dart`** : Modèles de données typés (`DesktopDevice`, `ScanEntry`, `AuthUser`, `SavedAccount`, `ProductDetails`, `BatchDetails`, `LocationItem`, `FefoViolationData`, `BulkDispatchItem`, `InventorySessionItem`, `InventorySummaryData`, `InventoryLineItem`, `InventoryScanResultData`, `InventoryScopeData`).
- **`views/`** : Dossier des vues graphiques et composants modulaires (`auth_dialog.dart`, `direct_inventory_view.dart`, `fast_dispatch_view.dart`, `physical_inventory_view.dart`, `remote_scanner_view.dart`, `scanner_camera_widget.dart`).
