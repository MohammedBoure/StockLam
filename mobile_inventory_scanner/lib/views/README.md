# Mobile Inventory Scanner Views (`lib/views`)

Ce sous-dossier regroupe les différentes vues de l'application mobile compagne Flutter.

## Fichiers et Rôles

- **`auth_dialog.dart`** : Boîte de dialogue de connexion sécurisée et feuille modale de gestion multi-comptes / multi-appareils avec persistance locale des sessions et déconnexion.
- **`direct_inventory_view.dart`** : Interface de gestion directe du stock sur mobile (recherche par code-barres / saisie manuelle de numéro, fiche produit, consultation des lots actifs, surlignage FEFO, validation sécurisée des consommations directes avec boîte de dialogue d'alerte FEFO et validation des transferts d'emplacement avec traçabilité utilisateur).
- **`fast_dispatch_view.dart`** : Interface de saisie rapide groupée multi-produits (similaire à `ui/widgets/inventory/tabs_dispatch.py`) avec basculement Consommation / Transfert, sélection d'emplacement par article ou commun, contrôle FEFO et validation en un clic.
- **`remote_scanner_view.dart`** : Interface de pont de scan distant transmettant les codes-barres directement vers le curseur de l'application bureau StockLam avec attribution utilisateur.
- **`scanner_camera_widget.dart`** : Composant de prévisualisation et de capture de code-barres via `mobile_scanner` avec gestion du basculement caméra avant/arrière et reprise après erreur.
