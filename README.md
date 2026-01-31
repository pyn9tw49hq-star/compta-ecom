# compta-ecom

Automatisation comptable e-commerce multi-canal : génération d'écritures comptables à partir des exports CSV Shopify, ManoMano, Decathlon et Leroy Merlin.

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
