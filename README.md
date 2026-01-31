# compta-ecom

Automatisation comptable e-commerce multi-canal : génération d'écritures comptables à partir des exports CSV Shopify, ManoMano, Decathlon et Leroy Merlin.

## Documentation

Un guide utilisateur complet est disponible dans [`docs/guide-utilisateur.md`](docs/guide-utilisateur.md) — il couvre la préparation des fichiers CSV, l'exécution, l'interprétation du fichier Excel de sortie, la personnalisation de la configuration et le dépannage.

## Prérequis

- Python 3.11+

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
compta-ecom <input_dir> <output_file> [--config-dir ./config/] [--log-level INFO]
```

- `input_dir` : répertoire contenant les fichiers CSV d'entrée
- `output_file` : fichier Excel de sortie
- `--config-dir` : répertoire de configuration YAML (défaut : `./config/`)
- `--log-level` : niveau de log — `DEBUG`, `INFO`, `WARNING`, `ERROR` (défaut : `INFO`)

## Build exécutable Windows

Générer un `.exe` autonome (aucune installation Python requise sur la machine cible) :

```bash
pip install -e ".[dev]"
python build.py
```

Le dossier `dist/` produit est prêt à zipper et distribuer :

```
dist/
├── compta-ecom.exe          # exécutable autonome
├── config/                  # configuration YAML modifiable
│   ├── channels.yaml
│   ├── chart_of_accounts.yaml
│   └── vat_table.yaml
└── guide-utilisateur.md     # documentation utilisateur
```

Sur la machine cible, lancer :

```
compta-ecom.exe <input_dir> <output_file> [--config-dir ./config/]
```
