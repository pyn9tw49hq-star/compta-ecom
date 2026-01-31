"""Script de build PyInstaller — génère dist/ prêt à distribuer.

Produit :
    dist/
    ├── compta-ecom.exe
    ├── config/          (modifiable par l'utilisateur)
    └── guide-utilisateur.md

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


def main() -> None:
    """Point d'entrée du script de build."""
    if not SRC_MAIN.exists():
        print(f"ERREUR : {SRC_MAIN} introuvable", file=sys.stderr)
        sys.exit(1)
    if not CONFIG_SRC.is_dir():
        print(f"ERREUR : dossier {CONFIG_SRC} introuvable", file=sys.stderr)
        sys.exit(1)
    if not GUIDE_SRC.exists():
        print(f"ERREUR : {GUIDE_SRC} introuvable", file=sys.stderr)
        sys.exit(1)

    _run_pyinstaller()
    _copy_config()
    _copy_guide()

    print()
    print("Build terminé. Contenu de dist/ :")
    for item in sorted(DIST_DIR.iterdir()):
        suffix = "/" if item.is_dir() else ""
        print(f"  {item.name}{suffix}")


if __name__ == "__main__":
    main()
