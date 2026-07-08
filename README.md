# BPM Metronome

A small vibe-coded desktop tool for generating very precise metronome WAV files.

It is useful when you need an exact BPM or interval-based click track, with a custom beep sound that can be tuned and saved as reusable profiles.

![Capture d'écran 2026-07-08 204718.png](icon/Capture%20d%27%C3%A9cran%202026-07-08%20204718.png)

## Features

- Generate precise `.wav` metronome files from a BPM or a time interval in seconds.
- Choose the duration of the generated audio in minutes.
- Configure two beeps (strong / weak) with duration, frequency, brightness, decay, and volume.
- Choose the number of beats per measure and mark each beat as strong or weak by clicking on circles.
- Preview a single beep, or preview the full measure looped over 2 bars.
- Save, load, and delete profiles that store both beeps and the accent pattern.
- Rename, replay, open, refresh, and delete generated metronome files from the app.

## How To Use

1. Run the app:

   ```powershell
   python src/main.py
   ```

2. Choose the mode:
   - `Intervalle en secondes` for exact spacing between clicks.
   - `BPM` for a classic beats-per-minute value.

3. Enter the value and the duration in minutes.

4. Adjust the strong and weak beep settings, or load a saved profile.

5. Choose the number of beats per measure, then click the circles to set which beats are strong (lit) or weak (empty).

6. Click `Previsualiser bip` to test one sound, or `Previsualiser mesure` to hear the full pattern.

7. Click `Sauvegarder WAV` to generate the metronome file.

Generated files are stored in the app data folder and can be managed directly from the interface.

## Project structure

The code lives in `src/`, organized by feature:

```text
src/
├── main.py                     # entry point, starts the GUI
└── features/
    ├── shared/                 # cross-cutting code
    │   ├── constants.py        # audio + click defaults, presets, app name
    │   ├── paths.py            # app data directories
    │   └── utils.py            # number parsing, filenames, file opening
    ├── audio/
    │   ├── core.py             # click synthesis (pure domain)
    │   └── usecase.py          # writing WAV files
    ├── click_profiles/
    │   ├── core.py             # profile validation
    │   └── repository.py       # loading/saving profiles
    ├── metronomes/
    │   ├── core.py             # input validation + timing computation
    │   ├── repository.py       # generated files + index.json access
    │   └── usecase.py          # generate metronome, cache lookup
    └── gui/
        └── app.py              # tkinter interface (view + controller)
```

## Changelog

### 1.1.0

- Reorganized the codebase into a feature-based `src/` layout.
- Added two configurable beeps (strong / weak) with duration, frequency, brightness, decay, and volume.
- Added beats-per-measure selection with a clickable accent pattern (strong = lit circle, weak = empty).
- The entered value (interval or BPM) now defines the full measure; beats subdivide it.
- Added a full-measure preview looped over 2 bars.
- Profiles now store both beeps and the accent pattern (old single-beep profiles are migrated automatically).
- Reworked beep settings with sliders plus an editable value and preset buttons.
- Display the app version in the bottom-right corner.

### 1.0.0

- Initial release: generate precise metronome WAV files from a BPM or interval, with a customizable beep and reusable profiles.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

