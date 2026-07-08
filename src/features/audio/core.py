import math

from features.shared.constants import CLICK_GAIN, CLICK_MAIN_LEVEL, SAMPLE_RATE


def make_click(duration_s, frequency_hz, brightness, decay, level=1.0):
        """
        Crée le clic avec les réglages demandés.
        Ensuite, on le recopie dans le WAV aux bons endroits.
        """
        click_samples = int(duration_s * SAMPLE_RATE)
        click = []

        for n in range(click_samples):
                t = n / SAMPLE_RATE

                envelope = math.exp(-t * decay)

                value = level * envelope * (
                            CLICK_MAIN_LEVEL * math.sin(2 * math.pi * frequency_hz * t)
                            + brightness * math.sin(2 * math.pi * frequency_hz * 2 * t)
                )

                # Gain volontairement inférieur à 1 pour éviter le clipping
                value *= CLICK_GAIN

                sample = int(max(-1.0, min(1.0, value)) * 32767)
                click.append(sample)

        return click


def make_click_from_config(beep):
        """Construit un clic à partir d'une config de bip (dict avec clés click_*)."""
        return make_click(
                duration_s=beep["click_duration_s"],
                frequency_hz=beep["click_frequency_hz"],
                brightness=beep["click_brightness"],
                decay=beep["click_decay"],
                level=beep.get("click_level", 1.0),
        )
