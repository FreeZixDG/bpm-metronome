import time

from features.audio.usecase import generate_wav
from features.metronomes.repository import default_filename_from_bpm, unique_path
from features.shared.constants import (
        DEFAULT_CLICK_BRIGHTNESS,
        DEFAULT_CLICK_DECAY,
        DEFAULT_CLICK_DURATION_S,
        DEFAULT_CLICK_FREQUENCY_HZ,
        SAMPLE_RATE,
)
from features.shared.paths import OUT_DIR


def find_cached_entry(entries, params):
        for entry in entries:
                entry_click_duration_s = entry.get("click_duration_s", DEFAULT_CLICK_DURATION_S)
                entry_click_frequency_hz = entry.get("click_frequency_hz", DEFAULT_CLICK_FREQUENCY_HZ)
                entry_click_brightness = entry.get("click_brightness", DEFAULT_CLICK_BRIGHTNESS)
                entry_click_decay = entry.get("click_decay", DEFAULT_CLICK_DECAY)

                same_click = (
                            abs(entry_click_duration_s - params["click_duration_s"]) < 1e-9
                            and abs(entry_click_frequency_hz - params["click_frequency_hz"]) < 1e-9
                            and abs(entry_click_brightness - params["click_brightness"]) < 1e-9
                            and abs(entry_click_decay - params["click_decay"]) < 1e-9
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
                click_params=params,
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
                "click_duration_s": params["click_duration_s"],
                "click_frequency_hz": params["click_frequency_hz"],
                "click_brightness": params["click_brightness"],
                "click_decay": params["click_decay"],
                "created_at": time.time(),
        }
