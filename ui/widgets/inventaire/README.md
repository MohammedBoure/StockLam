# UI Widgets - Inventaire (`ui/widgets/inventaire`)

Ce sous-dossier regroupe les composants graphiques PySide6 dédiés à la gestion et au contrôle des sessions d'inventaire physique dans StockLam / MODERNSTOCK.

## Fichiers et Rôles

- **`__init__.py`** : Expose les classes principales (`InventoryCountTab`, `NewInventorySessionDialog`, `InventoryCountScanDialog`).
- **`inventory_count_tab.py`** : Onglet principal d'inventaire bureautique (`InventoryCountTab`) permettant de lister les sessions avec badges de statut (`Counting`, `Review`, `Applied`, `Cancelled`), d'analyser les indicateurs clés (OK, Manquants, Excédents, Non comptés, Inconnus, Écart financier estimé), de créer de nouvelles sessions (`NewInventorySessionDialog`), de passer en revue, d'exporter sous Excel et d'appliquer les ajustements au stock réel.
- **`inventory_count_scan_dialog.py`** : Boîte de dialogue de comptage rapide (`InventoryCountScanDialog`) avec saisie de code-barres (douchette ou clavier), affichage en temps réel des informations de lot/produit, ajustement de quantité comptée et historique des scans de la session.
