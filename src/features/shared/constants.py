SAMPLE_RATE = 48_000

DEFAULT_CLICK_DURATION_S = 0.035
DEFAULT_CLICK_FREQUENCY_HZ = 1800
DEFAULT_CLICK_BRIGHTNESS = 0.35
DEFAULT_CLICK_DECAY = 140

CLICK_GAIN = 0.65
CLICK_MAIN_LEVEL = 0.85

CLICK_SETTING_PRESETS = {
        "duration": [
                ("Court", 0.02),
                ("Moyen", DEFAULT_CLICK_DURATION_S),
                ("Long", 0.08),
        ],
        "frequency": [
                ("Grave", 1200),
                ("Moyen", DEFAULT_CLICK_FREQUENCY_HZ),
                ("Aigu", 2600),
        ],
        "brightness": [
                ("Faible", 0.1),
                ("Moyenne", DEFAULT_CLICK_BRIGHTNESS),
                ("Forte", 0.6),
        ],
        "decay": [
                ("Long", 60),
                ("Moyen", DEFAULT_CLICK_DECAY),
                ("Court", 220),
        ],
}

DEFAULT_CLICK_PROFILES = [
        {
                "name": "default",
                "click_duration_s": DEFAULT_CLICK_DURATION_S,
                "click_frequency_hz": float(DEFAULT_CLICK_FREQUENCY_HZ),
                "click_brightness": DEFAULT_CLICK_BRIGHTNESS,
                "click_decay": float(DEFAULT_CLICK_DECAY),
        }
]

APP_NAME = "BPM Metronome"
LEGACY_APP_NAMES = ["BNM Metronome"]
