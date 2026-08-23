# StockLam External API (`api`)

Ce dossier contient l'infrastructure de service REST et de découverte réseau pour permettre aux périphériques mobiles (smartphones, douchettes WiFi, scanners Android/iOS) d'interagir directement et de façon sécurisée avec la base de données et l'application StockLam.

## Architecture et Sécurité

Le serveur API s'exécute sur le réseau local (LAN/WiFi).
- **Authentification** : Chaque requête doit inclure l'en-tête `X-API-Key` ou `Authorization: Bearer <TOKEN>`.
- **Découverte automatique (UDP Discovery)** : Le serveur répond sur le port UDP 8788 aux requêtes de broadcast `STOCKLAM_DISCOVER_V1` pour configurer automatiquement les téléphones sans saisie d'IP.
- **Règles métier de Stock & FEFO** : Les opérations de consommation et de transfert respectent rigoureusement les mêmes règles de traçabilité, de validation de stock et de priorité FEFO/FIFO que l'interface bureautique `ui/widgets/inventory/tabs_dispatch.py`.

## Fichiers du Répertoire

- **`__init__.py`** : Point d'entrée principal exposant les constructeurs de serveurs (`build_server`, `build_discovery_server`) et les constantes globales.
- **`auth.py`** : Validation des jetons d'accès et politiques de sécurité API.
- **`discovery.py`** : Serveur de découverte UDP pour la détection automatique du PC hôte sur le réseau local.
- **`server.py`** : Routeur HTTP multithreadé (`StockLamApiServer`, `StockLamApiHandler`) gérant la sérialisation JSON, CORS et l'aiguillage des requêtes.
- **`services/`** : Couche de services métier (résolution code-barres, consommation, transfert, FEFO, inventaires, emplacements).

## Spécification des Points d'Accès (Endpoints)

| Méthode | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Vérification de l'état du serveur, nom du poste et capacités supportées |
| `GET` | `/api/users/list` | Liste des utilisateurs actifs pour sélection et attribution mobile |
| `POST` | `/api/auth/login` | Authentification utilisateur par mot de passe avec profil et permissions |
| `GET` | `/api/barcode/lookup?barcode=...` | Résolution d'un code-barres (produit, lots actifs, recommandations FEFO) |
| `GET` | `/api/stock/fefo-check?batch_id=...` | Analyse et conformité FEFO/FIFO pour un lot spécifique |
| `GET` | `/api/locations` | Liste des emplacements de stockage disponibles pour les transferts |
| `POST` | `/api/stock/consume` | Consommation directe sécurisée avec traçabilité utilisateur, notes et contrôle FEFO |
| `POST` | `/api/stock/transfer` | Transfert de lot vers un nouvel emplacement avec traçabilité utilisateur |
| `POST` | `/api/stock/bulk-dispatch` | Saisie groupée multi-produits (sorties ou transferts groupés avec emplacements dédiés) |
| `POST` | `/api/remote-scans` | Pont de saisie distante directe vers le champ actif de l'application bureau |
| `GET` | `/api/inventory-scopes` | Liste des périmètres (emplacements, familles) pour la création de session |
| `GET` | `/api/inventory-sessions` | Liste des sessions de comptage d'inventaire physique (avec filtres status/year/limit) |
| `POST` | `/api/inventory-sessions` | Création d'une nouvelle session d'inventaire avec snapshot |
| `GET` | `/api/inventory-sessions/<id>` | Détails complets et résumé d'une session d'inventaire |
| `GET` | `/api/inventory-sessions/<id>/summary` | Résumé chiffré et financier d'une session d'inventaire |
| `GET` | `/api/inventory-sessions/<id>/lookup?barcode=...` | Recherche de ligne par code-barres dans la session |
| `GET` | `/api/inventory-sessions/<id>/lines?status=...&search=...` | Liste des lignes d'audit avec filtres par statut et recherche |
| `POST` | `/api/inventory-sessions/<id>/scan` | Enregistrement d'un comptage individuel de code-barres |
| `POST` | `/api/inventory-sessions/<id>/bulk-scan` | Synchronisation de scans groupés hors-ligne |
| `PUT` / `POST` | `/api/inventory-sessions/<id>/lines/<line_id>` | Correction manuelle de la quantité comptée d'une ligne |
| `POST` | `/api/inventory-sessions/<id>/review` | Passage de la session en revue (fin de comptage) |
| `POST` | `/api/inventory-sessions/<id>/apply` | Application des écarts constatés sur le stock réel |
| `POST` | `/api/inventory-sessions/<id>/cancel` | Annulation de la session sans appliquer les écarts |
| `DELETE` / `POST` | `/api/inventory-sessions/<id>` (`/delete`) | Suppression complète d'une session d'inventaire |
