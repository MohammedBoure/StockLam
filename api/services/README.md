# API Services Layer (`api/services`)

Ce sous-dossier regroupe les services métier utilisés par le serveur API pour exécuter les opérations de stock de façon modulaire, sécurisée et découplée des gestionnaires graphiques.

## Fichiers et Responsabilités

- **`__init__.py`** : Expose l'ensemble des fonctions de service pour le serveur API.
- **`barcode_service.py`** : Résolution et recherche des codes-barres internes (`Internal_Barcode`) et fabricants (`Barcode`), agrégation des lots disponibles et marquage du lot recommandé.
- **`dispatch_service.py`** : Logique d'exécution de la consommation directe (`safe_consume`) avec détection d'infraction FEFO et des transferts d'emplacement (`safe_transfer`).
- **`fefo_service.py`** : Moteur de calcul de conformité FEFO (First Expired, First Out) et FIFO (First In, First Out) garantissant l'utilisation prioritaire des réactifs les plus anciens.
- **`inventory_count_service.py`** : Gestion des sessions de comptage d'inventaire physique mobile (listage, résumé, consultation et scan de ligne).
- **`location_service.py`** : Récupération de la liste aplatie des emplacements de stockage avec leur arborescence hiérarchique.
