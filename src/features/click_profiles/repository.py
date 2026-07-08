import json

from features.click_profiles.core import has_default_profile, normalize_profile
from features.shared.constants import DEFAULT_CLICK_PROFILES
from features.shared.paths import APP_DATA_DIR, CLICK_PROFILES_FILE


def load_click_profiles():
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

        if not CLICK_PROFILES_FILE.exists():
                save_click_profiles(DEFAULT_CLICK_PROFILES)
                return [dict(profile) for profile in DEFAULT_CLICK_PROFILES]

        try:
                with CLICK_PROFILES_FILE.open("r", encoding="utf-8") as f:
                        data = json.load(f)
        except Exception:
                return []

        if not isinstance(data, list):
                return []

        profiles = []

        for profile in data:
                normalized = normalize_profile(profile)

                if normalized is not None:
                        profiles.append(normalized)

        if not has_default_profile(profiles):
                profiles = [dict(profile) for profile in DEFAULT_CLICK_PROFILES] + profiles
                save_click_profiles(profiles)

        return profiles


def save_click_profiles(profiles):
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

        with CLICK_PROFILES_FILE.open("w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
