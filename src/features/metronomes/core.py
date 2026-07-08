from features.shared.constants import SAMPLE_RATE
from features.shared.utils import format_float, parse_float_expression


def parse_click_params(duration_text, frequency_text, brightness_text, decay_text, level_text):
        """Analyse et valide les réglages d'un bip. Lève ValueError si invalide."""
        click_duration_s = parse_float_expression(duration_text)
        click_frequency_hz = parse_float_expression(frequency_text)
        click_brightness = parse_float_expression(brightness_text)
        click_decay = parse_float_expression(decay_text)
        click_level = parse_float_expression(level_text)

        if click_duration_s <= 0:
                raise ValueError("La durée du bip doit être positive.")

        if click_frequency_hz <= 0:
                raise ValueError("La fréquence du bip doit être positive.")

        max_click_frequency_hz = SAMPLE_RATE / 4

        if click_frequency_hz >= max_click_frequency_hz:
                raise ValueError(
                        f"La fréquence du bip doit être inférieure à {format_float(max_click_frequency_hz)} Hz."
                )

        if click_brightness < 0:
                raise ValueError("La brillance doit être positive ou nulle.")

        if click_decay <= 0:
                raise ValueError("Le decay doit être positif.")

        if click_level <= 0:
                raise ValueError("Le volume du bip doit être positif.")

        return {
                "click_duration_s": click_duration_s,
                "click_frequency_hz": click_frequency_hz,
                "click_brightness": click_brightness,
                "click_decay": click_decay,
                "click_level": click_level,
        }


def parse_metronome_params(mode, value_text, duration_text, strong_beep, weak_beep, pattern):
        """Analyse les entrées principales et calcule le timing du métronome."""
        value = parse_float_expression(value_text)
        duration_min = parse_float_expression(duration_text)

        if value <= 0:
                raise ValueError("La valeur doit être positive.")

        if duration_min <= 0:
                raise ValueError("La durée doit être positive.")

        if not pattern:
                raise ValueError("Il faut au moins un temps.")

        beats = len(pattern)
        duration_s = duration_min * 60

        # La valeur (intervalle ou BPM) décrit la mesure complète (le battement).
        if mode == "bpm":
                requested_bpm = value
                requested_interval_s = 60 / requested_bpm
        else:
                requested_interval_s = value
                requested_bpm = 60 / requested_interval_s

        # Les temps subdivisent la mesure : l'écart entre deux bips = mesure / nb temps.
        beat_interval_s = requested_interval_s / beats
        samples_between = round(beat_interval_s * SAMPLE_RATE)

        if samples_between <= 0:
                raise ValueError("Intervalle trop court.")

        # Timing réellement représenté dans le WAV (durée réelle de la mesure)
        actual_interval_s = (samples_between * beats) / SAMPLE_RATE
        actual_bpm = 60 / actual_interval_s

        return {
                "mode": mode,
                "requested_bpm": requested_bpm,
                "requested_interval_s": requested_interval_s,
                "actual_bpm": actual_bpm,
                "actual_interval_s": actual_interval_s,
                "samples_between": samples_between,
                "duration_s": duration_s,
                "beats": beats,
                "pattern": [bool(x) for x in pattern],
                "strong": dict(strong_beep),
                "weak": dict(weak_beep),
        }
