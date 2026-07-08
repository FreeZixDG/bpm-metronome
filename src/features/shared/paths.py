import os
import sys
from pathlib import Path

from features.shared.config import DEBUG, DEBUG_DATA_DIR
from features.shared.constants import APP_NAME, LEGACY_APP_NAMES


def get_platform_app_data_dir(app_name):
        if sys.platform.startswith("win"):
                appdata = os.getenv("APPDATA")

                if appdata:
                        return Path(appdata) / app_name

        return Path.home() / f".{app_name.lower().replace(' ', '-')}"


def get_app_data_dir():
        app_data_dir = get_platform_app_data_dir(APP_NAME)

        for legacy_app_name in LEGACY_APP_NAMES:
                legacy_app_data_dir = get_platform_app_data_dir(legacy_app_name)

                if legacy_app_data_dir.exists() and not app_data_dir.exists():
                        try:
                                legacy_app_data_dir.rename(app_data_dir)
                        except Exception:
                                pass

                        break

        return app_data_dir


APP_DATA_DIR = DEBUG_DATA_DIR if DEBUG else get_app_data_dir()
OUT_DIR = APP_DATA_DIR / "metros"
DB_FILE = OUT_DIR / "index.json"
CLICK_PROFILES_FILE = APP_DATA_DIR / "click_profiles.json"
