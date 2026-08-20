# Utilitaires et Outils Système (`tools`)

Ce répertoire contient des scripts utilitaires pour la maintenance, l'audit de stock, les corrections de cohérence de données et le lancement du serveur API externe.

## Fichiers et Rôles

- **`audit_reception_stock.py`** : Script d'audit et de vérification de cohérence entre réceptions et lots d'inventaire.
- **`export_bad_lot_products.py`** : Exportation des produits présentant des anomalies de numéros de lot.
- **`inventory_mobile_api.py`** : Point d'entrée CLI pour démarrer le serveur API externe en mode autonome (`--host`, `--port`).
- **`mobile_barcode_bridge.py`** : Pont de communication entre les scans distants (via API) et les champs de saisie actifs de l'interface graphique PyQt.
- **`repair_legacy_reception_splits.py`** : Script de réparation pour les historiques de réceptions fractionnées.
- **`repair_reception_stock_consistency.py`** : Script de correction de la cohérence comptable et physique des réceptions.
- **`start_inventory_mobile_api.ps1`** : Script PowerShell pour le lancement automatisé du serveur API avec gestion de l'environnement virtuel.
- **`update_environment_setup_checklist.py`** : Utilitaire de mise à jour des prérequis d'environnement et de dépendances.
