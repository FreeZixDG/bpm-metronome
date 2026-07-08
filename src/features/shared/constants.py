SAMPLE_RATE = 48_000

DEFAULT_CLICK_DURATION_S = 0.035
DEFAULT_CLICK_FREQUENCY_HZ = 1800
DEFAULT_CLICK_BRIGHTNESS = 0.35
DEFAULT_CLICK_DECAY = 140
DEFAULT_CLICK_LEVEL = 1.0

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
        "level": [
                ("Fort", 1.0),
                ("Moyen", 0.6),
                ("Faible", 0.3),
        ],
}

# Un "bip" est un son complet : durée, fréquence, brillance, decay et volume.
DEFAULT_STRONG_BEEP = {
        "click_duration_s": DEFAULT_CLICK_DURATION_S,
        "click_frequency_hz": float(DEFAULT_CLICK_FREQUENCY_HZ),
        "click_brightness": DEFAULT_CLICK_BRIGHTNESS,
        "click_decay": float(DEFAULT_CLICK_DECAY),
        "click_level": 1.0,
}
DEFAULT_WEAK_BEEP = {
        "click_duration_s": DEFAULT_CLICK_DURATION_S,
        "click_frequency_hz": 1400.0,
        "click_brightness": 0.2,
        "click_decay": float(DEFAULT_CLICK_DECAY),
        "click_level": 0.5,
}

# Pattern d'accents : True = bip fort, False = bip faible.
MAX_BEATS = 12
BEAT_CHOICES = list(range(1, MAX_BEATS + 1))
DEFAULT_BEATS = 4
DEFAULT_PATTERN = [True, False, False, False]

DEFAULT_CLICK_PROFILES = [
        {
                "name": "default",
                "beats": DEFAULT_BEATS,
                "pattern": list(DEFAULT_PATTERN),
                "strong": dict(DEFAULT_STRONG_BEEP),
                "weak": dict(DEFAULT_WEAK_BEEP),
        }
]

APP_NAME = "BPM Metronome"
APP_VERSION = "1.0.0"
LEGACY_APP_NAMES = ["BNM Metronome"]
