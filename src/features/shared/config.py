from pathlib import Path

# En mode debug, les données sont stockées dans le dossier "data" du dépôt
# plutôt que dans AppData. Pratique pour tester sans polluer AppData.
DEBUG = True

# Racine du dépôt : config.py -> shared -> features -> src -> racine
REPO_ROOT = Path(__file__).resolve().parents[3]
DEBUG_DATA_DIR = REPO_ROOT / "data"
