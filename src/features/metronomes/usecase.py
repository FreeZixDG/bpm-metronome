import time

from features.audio.usecase import generate_wav
from features.click_profiles.core import BEEP_KEYS
from features.metronomes.repository import default_filename_from_bpm, unique_path
from features.shared.constants import SAMPLE_RATE
from features.shared.paths import OUT_DIR


def _beeps_equal(a, b):
        if not isinstance(a, dict) or not isinstance(b, dict):
                return False

        for key in BEEP_KEYS:
                if abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0))) >= 1e-9:
                        return False

        return True


def find_cached_entry(entries, params):
        for entry in entries:
                strong = entry.get("strong")
                weak = entry.get("weak")
                pattern = entry.get("pattern")

                if not (isinstance(strong, dict) and isinstance(weak, dict) and isinstance(pattern, list)):
                        continue

                same_click = (
                            _beeps_equal(strong, params["strong"])
                            and _beeps_equal(weak, params["weak"])
                            and [bool(x) for x in pattern] == params["pattern"]
                )
                same_timing = (
                            entry.get("sample_rate") == SAMPLE_RATE
                            and entry.get("samples_between") == params["samples_between"]
                            and abs(entry.get("duration_s", 0) - params["duration_s"]) < 1e-9
                )

                path = OUT_DIR / entry.get("filename", "")

                if same_timing and same_click and path.exists():
                        return entry

        return None


def generate_metronome(params):
        """Génère le fichier WAV et retourne l'entrée décrivant le métronome."""
        filename = default_filename_from_bpm(params["requested_bpm"])
        path = unique_path(filename)

        generate_wav(
                path=path,
                duration_s=params["duration_s"],
                samples_between=params["samples_between"],
                strong_beep=params["strong"],
                weak_beep=params["weak"],
                pattern=params["pattern"],
        )

        return {
                "filename": path.name,
                "sample_rate": SAMPLE_RATE,
                "duration_s": params["duration_s"],
                "requested_bpm": params["requested_bpm"],
                "requested_interval_s": params["requested_interval_s"],
                "actual_bpm": params["actual_bpm"],
                "actual_interval_s": params["actual_interval_s"],
                "samples_between": params["samples_between"],
                "beats": params["beats"],
                "pattern": list(params["pattern"]),
                "strong": dict(params["strong"]),
                "weak": dict(params["weak"]),
                "created_at": time.time(),
        }
