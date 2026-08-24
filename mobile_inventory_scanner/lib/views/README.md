# Mobile Inventory Scanner Views (`lib/views`)

Ce sous-dossier regroupe les différentes vues de l'application mobile compagne Flutter.

## Fichiers et Rôles

- **`auth_dialog.dart`** : Boîte de dialogue de connexion sécurisée et feuille modale de gestion multi-comptes / multi-appareils avec persistance locale des sessions et déconnexion.
- **`direct_inventory_view.dart`** : Interface de gestion directe du stock sur mobile (recherche par code-barres / saisie manuelle de numéro, fiche produit, consultation des lots actifs, surlignage FEFO, validation sécurisée des consommations directes avec boîte de dialogue d'alerte FEFO et validation des transferts d'emplacement avec traçabilité utilisateur).
- **`fast_dispatch_view.dart`** : Interface de saisie rapide groupée multi-produits (conforme à `ui/widgets/inventory/tabs_dispatch.py`) avec sélecteur d'emplacement source direct par carte (dropdown listant tous les emplacements où le produit est stocké), ajout de nouvelle ligne à chaque scan successif d'un même produit/code-barres, suppression individuelle par bouton '✕' ou vidage global, retours sonore et haptique immersifs, surlignage dynamique des cartes, scan caméra continu auto-réarmé, basculement Consommation / Transfert et validation en un clic.
- **`physical_inventory_view.dart`** : Interface de comptage et d'audit d'inventaire physique (gestion et création de session avec périmètre ALL/LOCATION/FAMILY, comptage caméra continu avec retour haptique, fiches d'écart et de conformité instantanée, mode remplacement ou accumulation, liste filtrable avec recherche et modification manuelle de chaque ligne, clôture de session, choix de gestion des non-comptés et application des ajustements au stock réel).
- **`remote_scanner_view.dart`** : Interface de pont de scan distant transmettant les codes-barres directement vers le curseur de l'application bureau StockLam avec attribution utilisateur.
- **`scanner_camera_widget.dart`** : Composant de prévisualisation et de capture de code-barres via `mobile_scanner` avec gestion du basculement caméra avant/arrière et reprise après erreur.
