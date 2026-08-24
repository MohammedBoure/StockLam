# Module Achats & Approvisionnements (`ui/widgets/procurement`)

Ce dossier contient l ensemble des composants d interface utilisateur pour la gestion des commandes d achat (Bons de commande), des réceptions de marchandises (Bons de réception), des avoirs fournisseurs et des impressions d étiquettes de codes-barres.

## Fichiers et Rôles

- **`procurement_tabs.py`** : Conteneur principal d onglets pour le module Achats (`ProcurementTab`, `PurchaseOrdersTab`) avec barre d outils, export PDF et orchestration des sous-onglets.
- **`po_list_view.py`** : Tableau d affichage et de suivi des bons de commande (`PurchaseOrderListView`) avec filtrage par statut/fournisseur, tri numérique et montant estimé TTC calculé dynamiquement depuis le stock.
- **`dialogs.py`** : Fenêtres modales de création/édition de commandes d achat (`PurchaseOrderDialog`) avec calcul en direct des montants estimés TTC (P.U et totaux) et alertes de stock (`StockAlertDialog`).
- **`reception_tab.py`** : Onglet listant les commandes en attente de réception (`ReceptionTab`) pour initier les bons de réception.
- **`reception_history_tab.py`** : Historique et consultation des bons de réception enregistrés (`ReceptionHistoryTab`).
- **`reception_dialog_parts.py`** : Composants réutilisables d en-tête et de formulaire pour la saisie des réceptions.
- **`barcode_summary_dialog.py`** : Dialogue récapitulatif des codes-barres générés lors de la réception pour configuration et impression directe des étiquettes.
- **`bulk_barcode_selection_dialog.py`** : Dialogue de sélection par lot pour l impression groupée d étiquettes de lots reçus.
- **`location_tree_combo.py`** : Sélecteur arborescent d emplacements de stockage pour l affectation rapide des réceptions.

## Sous-dossiers

- **`avoir/`** : Gestion des avoirs et notes de crédit fournisseurs.
- **`reception_dialog/`** : Boîte de dialogue modulaire de réception de marchandises (`ReceptionDialog`, logique financière et d inventaire).
