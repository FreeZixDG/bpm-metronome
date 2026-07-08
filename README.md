# BPM Metronome

A small vibe-coded desktop tool for generating very precise metronome WAV files.

It is useful when you need an exact BPM or interval-based click track, with a custom beep sound that can be tuned and saved as reusable profiles.

![BPM Metronome screenshot](icon/screenshot.png)

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

