# Module Avoirs Fournisseurs (`ui/widgets/procurement/avoir`)

Ce dossier contient l'ensemble des composants d'interface utilisateur pour la gestion des avoirs et notes de crédit fournisseurs (retour de marchandise avec ajustement de stock ou correction financière de prix).

## Fichiers et Rôles

- **`CreditNoteTab.py`** : Conteneur principal d'onglets pour le sous-module Avoirs (`CreditNoteTab`), assurant la navigation entre la liste des avoirs enregistrés et le formulaire de saisie.
- **`CreditNoteList.py`** : Vue tabulaire de consultation et de recherche des avoirs fournisseurs (`CreditNoteList`) avec filtres par date, menu contextuel (modification/suppression) et affichage formaté des montants TTC.
- **`CreditNoteForm.py`** : Formulaire complet de saisie et de modification d'un avoir fournisseur (`CreditNoteForm`) avec validation d'en-tête, liaison avec un Bon de Réception (BR), recherche de produit/code-barres, gestion des lots/dates de péremption, calcul automatique des montants et persistance immédiate.
- **`BatchSelectionDialog.py`** : Fenêtre modale de sélection de lot (`BatchSelectionDialog`) affichée lorsqu'un produit à retourner dispose de plusieurs lots/réceptions, permettant à l'utilisateur de choisir le lot exact concerné.
- **`__init__.py`** : Initialisation du package Python et export des composants principaux (`CreditNoteTab`, `CreditNoteForm`, `CreditNoteList`, `BatchSelectionDialog`).
