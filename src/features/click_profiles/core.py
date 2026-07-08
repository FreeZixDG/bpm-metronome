from features.shared.constants import (
        DEFAULT_BEATS,
        DEFAULT_STRONG_BEEP,
        DEFAULT_WEAK_BEEP,
        MAX_BEATS,
)

BEEP_KEYS = (
        "click_duration_s",
        "click_frequency_hz",
        "click_brightness",
        "click_decay",
        "click_level",
)


def normalize_beep(raw, defaults):
        beep = dict(defaults)

        if isinstance(raw, dict):
                for key in BEEP_KEYS:
                        if key in raw:
                                try:
                                        beep[key] = float(raw[key])
                                except (TypeError, ValueError):
                                        pass

        return beep


def normalize_pattern(raw, beats):
        pattern = [bool(x) for x in raw] if isinstance(raw, list) else []

        if len(pattern) < beats:
                pattern += [False] * (beats - len(pattern))
        else:
                pattern = pattern[:beats]

        return pattern


def normalize_profile(profile):
        """Valide et normalise un profil brut vers le schéma complet. None si invalide.

        Migre aussi les anciens profils (un seul bip à plat) : l'ancien son devient
        le bip fort, un bip faible par défaut est ajouté, sur un seul temps.
        """
        if not isinstance(profile, dict):
                return None

        name = str(profile.get("name", "")).strip()

        if not name:
                return None

        is_legacy = "strong" not in profile and "click_duration_s" in profile

        if is_legacy:
                return {
                        "name": name,
                        "beats": 1,
                        "pattern": [True],
                        "strong": normalize_beep(profile, DEFAULT_STRONG_BEEP),
                        "weak": dict(DEFAULT_WEAK_BEEP),
                }

        try:
                beats = int(profile.get("beats", DEFAULT_BEATS))
        except (TypeError, ValueError):
                beats = DEFAULT_BEATS

        beats = max(1, min(MAX_BEATS, beats))

        return {
                "name": name,
                "beats": beats,
                "pattern": normalize_pattern(profile.get("pattern"), beats),
                "strong": normalize_beep(profile.get("strong"), DEFAULT_STRONG_BEEP),
                "weak": normalize_beep(profile.get("weak"), DEFAULT_WEAK_BEEP),
        }


def has_default_profile(profiles):
        return any(profile["name"].strip().lower() == "default" for profile in profiles)


def find_profile(profiles, name):
        normalized_name = name.strip().lower()

        for profile in profiles:
                if profile["name"].strip().lower() == normalized_name:
                        return profile

        return None
