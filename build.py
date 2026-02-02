"""Script de build PyInstaller — génère dist/ prêt à distribuer.

Produit :
    dist/
    ├── 1_DEPOSER_CSV_ICI/
    │   └── Detail transactions par versements/   (optionnel — CSV Shopify par versement)
    ├── 2_RESULTATS/         (dossier vide pour les fichiers Excel)
    ├── config/              (configuration YAML modifiable)
    ├── compta-ecom.exe      (exécutable autonome)
    ├── guide-utilisateur.md
    └── LANCER.bat           (script de lancement pour l'utilisateur)

Usage :
    python build.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_MAIN = ROOT / "src" / "compta_ecom" / "main.py"
DIST_DIR = ROOT / "dist"
CONFIG_SRC = ROOT / "config"
GUIDE_SRC = ROOT / "docs" / "guide-utilisateur.md"
LANCER_SRC = ROOT / "LANCER.bat"


def _run_pyinstaller() -> None:
    """Lance PyInstaller pour créer l'exécutable unique."""
    cmd: list[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "compta-ecom",
        "--noconfirm",
        "--clean",
        # Ajouter src/ au path pour que les imports compta_ecom fonctionnent
        "--paths",
        str(ROOT / "src"),
        str(SRC_MAIN),
    ]
    print("[build] Lancement de PyInstaller…")
    subprocess.run(cmd, check=True)


def _copy_config() -> None:
    """Copie le dossier config/ dans dist/."""
    dest = DIST_DIR / "config"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CONFIG_SRC, dest)
    print(f"[build] config/ copié dans {dest}")


def _copy_guide() -> None:
    """Copie le guide utilisateur dans dist/."""
    dest = DIST_DIR / "guide-utilisateur.md"
    shutil.copy2(GUIDE_SRC, dest)
    print(f"[build] guide-utilisateur.md copié dans {dest}")


def _copy_lancer_bat() -> None:
    """Copie LANCER.bat dans dist/."""
    dest = DIST_DIR / "LANCER.bat"
    shutil.copy2(LANCER_SRC, dest)
    print(f"[build] LANCER.bat copié dans {dest}")


def _create_user_dirs() -> None:
    """Crée les dossiers utilisateur vides dans dist/."""
    for name in ("1_DEPOSER_CSV_ICI", "2_RESULTATS"):
        d = DIST_DIR / name
        d.mkdir(exist_ok=True)
        print(f"[build] dossier {name}/ créé dans {d}")
    # Sous-dossier pour les fichiers detail transactions (Epic 4)
    detail_dir = DIST_DIR / "1_DEPOSER_CSV_ICI" / "Detail transactions par versements"
    detail_dir.mkdir(exist_ok=True)
    print(f"[build] dossier Detail transactions par versements/ créé dans {detail_dir}")


def main() -> None:
    """Point d'entrée du script de build."""
    for label, path in [
        ("entry point", SRC_MAIN),
        ("config", CONFIG_SRC),
        ("guide", GUIDE_SRC),
        ("LANCER.bat", LANCER_SRC),
    ]:
        if not path.exists():
            print(f"ERREUR : {label} introuvable ({path})", file=sys.stderr)
            sys.exit(1)

    _run_pyinstaller()
    _copy_config()
    _copy_guide()
    _copy_lancer_bat()
    _create_user_dirs()

    print()
    print("Build terminé. Contenu de dist/ :")
    for item in sorted(DIST_DIR.iterdir()):
        suffix = "/" if item.is_dir() else ""
        print(f"  {item.name}{suffix}")


if __name__ == "__main__":
    main()
