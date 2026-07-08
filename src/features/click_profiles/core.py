def normalize_profile(profile):
        """Valide et normalise un profil brut. Retourne None si invalide."""
        if not isinstance(profile, dict):
                return None

        name = str(profile.get("name", "")).strip()

        if not name:
                return None

        try:
                click_duration_s = float(profile["click_duration_s"])
                click_frequency_hz = float(profile["click_frequency_hz"])
                click_brightness = float(profile["click_brightness"])
                click_decay = float(profile["click_decay"])
        except (KeyError, TypeError, ValueError):
                return None

        return {
                "name": name,
                "click_duration_s": click_duration_s,
                "click_frequency_hz": click_frequency_hz,
                "click_brightness": click_brightness,
                "click_decay": click_decay,
        }


def has_default_profile(profiles):
        return any(profile["name"].strip().lower() == "default" for profile in profiles)


def find_profile(profiles, name):
        normalized_name = name.strip().lower()

        for profile in profiles:
                if profile["name"].strip().lower() == normalized_name:
                        return profile

        return None
