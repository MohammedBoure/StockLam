# MODERNSTOCK Mobile Companion & Direct Stock Scanner

Application mobile Flutter compagne pour StockLam / MODERNSTOCK permettant d'effectuer la gestion directe du stock sur site et de servir de douchette code-barres sans fil.

## Modes de Fonctionnement

### 1. 📦 Mode Stock Direct (Inventaire & Dispatch sur site)
- **Recherche par Code-Barres ou Saisie Manuelle** : Scan caméra ou saisie directe du numéro de code-barres / numéro de lot.
- **Fiche Produit et Consultation des Lots** : Affichage du nom, famille, fabricant, unité et de tous les lots actifs avec leurs emplacements respectifs et dates de péremption.
- **Priorité FEFO Intelligente** : Surlignage du lot prioritaire (**⭐ RECOMMANDÉ**) selon la règle First Expired First Out.
- **Consommation Directe Sécurisée** : Sortie de stock avec alerte interactive et protection contre les infractions FEFO.
- **Transfert d'Emplacement Direct** : Changement d'emplacement avec sélection dans la liste des zones de stockage.

### 2. 📱 Mode Pont Bureau (Scanner sans fil)
- Scannez les codes-barres avec la caméra du téléphone pour les transmettre instantanément dans le champ actif du logiciel bureau.

## Connexion Réseau et Découverte

- **Découverte automatique (UDP)** : L'application détecte automatiquement les ordinateurs StockLam sur le réseau local (WiFi).
- **Configuration manuelle** : Saisie possible de l'adresse IP (`http://IP_DU_PC:8787`).

## Build et Développement

```powershell
flutter pub get
flutter analyze
flutter test

# Génération APK Release universel :
flutter build apk --release

# Génération APK par architecture (optimisé < 25 Mo) :
flutter build apk --split-per-abi --obfuscate --split-debug-info=build/symbols
```
