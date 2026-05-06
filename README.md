# StockLam / MODERNSTOCK

Application de gestion de stock avec deux brands depuis le même code source:

- `stocklam`: version générale, exe `StockLam`
- `modernstock`: version ModernLam, exe `MODERNSTOCK`

## Installation Dev

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Lancer la version par défaut:

```powershell
python main.py
```

Lancer un brand précis:

```powershell
python main.py stocklam
python main.py modernstock
```

Il est aussi possible d'utiliser:

```powershell
python main.py --brand modernstock
```

## Fichier `.env`

Le fichier `.env` est lu au démarrage. Il doit se trouver à la racine du projet en dev, ou à côté du `.exe` après compilation.

Exemple:

```env
FLASK_ENV=development
SECRET_KEY=change_me_key
MAX_CONTENT_LENGTH=16777216

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=Lab_Inventory_Enterprise_DB

DB_SCHEMA_CHECK_ON_STARTUP=false
```

Variables importantes:

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: connexion MySQL.
- `DB_SCHEMA_CHECK_ON_STARTUP`: contrôle le contrôle/migration de la base au démarrage.
  - `false`: démarrage rapide, recommandé en utilisation normale.
  - `true`: lance les `CREATE TABLE`, migrations, index et vérifications schema. À utiliser après une mise à jour DB, une nouvelle installation, ou si une migration est nécessaire.

Valeurs acceptées pour les booléens:

- vrai: `true`, `1`, `yes`, `y`, `on`
- faux: `false`, `0`, `no`, `n`, `off`

Important: le code utilise uniquement `DB_SCHEMA_CHECK_ON_STARTUP` dans `.env` pour ce comportement. Il n'y a pas de deuxième clé dans `config.json` pour éviter les conflits.

## Fichier `config.json`

`config.json` contient les réglages applicatifs modifiables depuis l'interface:

- informations laboratoire
- sauvegarde automatique
- imprimante et dimensions des étiquettes
- paramètres PDF et bannière
- paramètres DB affichés/exportés par l'écran Settings

Le bouton `Exporter .env` réécrit `.env` avec les paramètres DB, mais conserve `DB_SCHEMA_CHECK_ON_STARTUP` si la variable existe déjà.

## Compilation PyInstaller

Le script à utiliser est:

```powershell
python pyinstaller.py <brand>
```

Compiler StockLam:

```powershell
venv\Scripts\python.exe pyinstaller.py stocklam
```

Résultat:

```text
dist\StockLam\StockLam.exe
```

Compiler MODERNSTOCK:

```powershell
venv\Scripts\python.exe pyinstaller.py modernstock
```

Résultat:

```text
dist\MODERNSTOCK\MODERNSTOCK.exe
```

Compiler les deux:

```powershell
venv\Scripts\python.exe pyinstaller.py all
```

Le script copie automatiquement dans le dossier `dist\<exe_name>`:

- `.env`
- `config.json`
- assets du brand
- dossiers `documents` et `exports`

Après compilation, vérifie surtout:

- `dist\<exe_name>\.env`
- `dist\<exe_name>\config.json`
- `dist\<exe_name>\<exe_name>.exe`

## Ajouter Un Nouveau Brand

1. Créer un dossier:

```text
brand_assets\<brand_key>\
```

Exemple:

```text
brand_assets\newbrand\
```

2. Ajouter les images:

```text
brand_assets\newbrand\logo.png
brand_assets\newbrand\logo2.png
```

`logo2.png` est optionnel. Il sert de bannière si le brand l'utilise.

3. Ajouter `brand.json`:

```json
{
  "brand": "newbrand"
}
```

4. Ajouter le brand dans `branding.py`:

```python
BRANDS = {
    "newbrand": {
        "app_name": "NEWBRAND",
        "exe_name": "NEWBRAND",
        "organization_name": "NewBrand",
        "settings_app_name": "StockManager",
        "lock_file_name": "newbrand_stockmanager.lock",
        "logo": os.path.join("brand_assets", "newbrand", "logo.png"),
        "banner": os.path.join("brand_assets", "newbrand", "logo2.png"),
    },
}
```

5. Ajouter les alias dans `BRAND_ALIASES`:

```python
BRAND_ALIASES = {
    "newbrand": "newbrand",
    "new_brand": "newbrand",
}
```

6. Tester en dev:

```powershell
python main.py newbrand
```

7. Compiler:

```powershell
venv\Scripts\python.exe pyinstaller.py newbrand
```

## Notes De Maintenance

- Si le programme devient lent au démarrage, vérifie que `.env` contient:

```env
DB_SCHEMA_CHECK_ON_STARTUP=false
```

- Après une modification de structure DB, mettre temporairement:

```env
DB_SCHEMA_CHECK_ON_STARTUP=true
```

Lancer le programme une fois, puis remettre:

```env
DB_SCHEMA_CHECK_ON_STARTUP=false
```

- Ne pas garder deux copies différentes du même projet pour les brands. Le brand doit passer par `branding.py`, `brand_assets`, puis `pyinstaller.py`.
