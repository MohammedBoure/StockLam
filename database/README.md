# Database Layer (`database`)

Ce dossier regroupe tous les gestionnaires d'accès aux données (Managers), les modèles, les connexions et la logique métier de persistance pour StockLam.

## Fichiers et Rôles

- **`__init__.py`** : Point d'entrée du package database exposant les gestionnaires et les classes de base.
- **`active_container_manager.py`** : Gestion du cycle de vie des flacons/conteneurs ouverts (FEFO, suivi de la quantité restante, déclassement en déchet).
- **`auto_backup_worker.py`** : Worker asynchrone pour la sauvegarde automatisée de la base de données.
- **`automate_manager.py`** : Gestion des automates d'analyse du laboratoire et de leurs consommables associés.
- **`company_settings_manager.py`** : Configuration générale de l'entreprise, devise, seuils et paramètres globaux.
- **`credit_note_manager.py`** : Gestion des avoirs fournisseurs suite aux retours de marchandises.
- **`external_partners_manager.py`** : Gestion des partenaires externes (laboratoires confrères, cliniques partenaires).
- **`external_transfer_manager.py`** : Gestion des transferts et cessions de réactifs entre établissements.
- **`inventory_batch_manager.py`** : Gestion des lots en inventaire, réceptions, ajustements, péremptions et changements de statut.
- **`inventory_count_manager.py`** : Gestion des sessions de comptage d'inventaire physique et réconciliation d'écarts.
- **`location_manager.py`** : Gestion des emplacements de stockage (armoires, réfrigérateurs, congélateurs, tiroirs).
- **`manufacturer_manager.py`** : Gestion des fabricants et marques d'équipements / réactifs.
- **`packaging_unit_manager.py`** : Gestion des unités de conditionnement et facteurs de conversion.
- **`po_details_manager.py`** : Gestion des lignes de commandes d'achat et suivi de réception détaillée.
- **`printer_manager.py`** : Configuration des imprimantes d'étiquettes et paramètres d'impression code-barres.
- **`product_document_manager.py`** : Gestion des pièces jointes et fiches techniques (FDS / Notice) associées aux produits.
- **`product_family_manager.py`** : Gestion des familles et sous-familles de produits de laboratoire.
- **`product_manager.py`** : Gestion du catalogue maître des produits (`Products_Master`), seuils d'alerte et unités.
- **`purchase_order_manager.py`** : Gestion des bons de commande d'achat (`Purchase_Orders`) et cycle de validation.
- **`reception_log_manager.py`** : Journalisation et validation des réceptions de commandes avec calcul des coûts TTC et remises.
- **`statistics_manager.py`** : Calculs statistiques avancés, indicateurs clés (KPIs), valorisation de stock, flux réels, tendances d'achats/consommation et analyse détaillée des pertes et rebuts (`get_waste_analysis`, `get_waste_products_detailed`).
- **`stock_movement_log_manager.py`** : Traçabilité et historique immuable de tous les mouvements de stock (`Stock_Movement_Log`).
- **`supplier_manager.py`** : Gestion du référentiel des fournisseurs et historique des relations commerciales.
- **`system_log_manager.py`** : Enregistrement et consultation des journaux système et d'activité utilisateur.
- **`system_logger.py`** : Décorateurs et utilitaires de journalisation applicative standardisée.
- **`user_manager.py`** : Gestion des utilisateurs, authentification, rôles et permissions d'accès.
- **`waste_reason_manager.py`** : Référentiel des motifs de rebut et de perte (périmé, altéré, bris, etc.).
