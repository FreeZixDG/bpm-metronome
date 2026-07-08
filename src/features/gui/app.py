import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from features.audio.usecase import generate_click_preview_wav, generate_measure_preview_wav
from features.click_profiles.core import find_profile
from features.click_profiles.repository import load_click_profiles, save_click_profiles
from features.metronomes.core import parse_click_params, parse_metronome_params
from features.metronomes.repository import load_entries_from_files, save_db
from features.metronomes.usecase import find_cached_entry, generate_metronome
from features.shared.constants import (
        APP_VERSION,
        BEAT_CHOICES,
        CLICK_SETTING_PRESETS,
        DEFAULT_BEATS,
        DEFAULT_PATTERN,
        DEFAULT_STRONG_BEEP,
        DEFAULT_WEAK_BEEP,
        MAX_BEATS,
)
from features.shared.paths import OUT_DIR
from features.shared.utils import format_float, open_file, parse_float_expression, sanitize_filename

# (clé de preset, libellé affiché, clé dans la config du bip, min slider, max slider)
BEEP_SETTINGS = [
        ("duration", "Durée (s) :", "click_duration_s", 0.005, 0.15),
        ("frequency", "Fréquence (Hz) :", "click_frequency_hz", 200, 5000),
        ("brightness", "Brillance :", "click_brightness", 0.0, 1.0),
        ("decay", "Decay :", "click_decay", 20, 400),
        ("level", "Volume :", "click_level", 0.0, 1.0),
]

BEEP_RANGES = {key: (vmin, vmax) for key, _, _, vmin, vmax in BEEP_SETTINGS}

BEEP_TYPES = [
        ("strong", "Bip fort", DEFAULT_STRONG_BEEP),
        ("weak", "Bip faible", DEFAULT_WEAK_BEEP),
]

CIRCLE_RADIUS = 16
CIRCLE_GAP = 16
CIRCLE_MARGIN = 14
CIRCLE_STRONG_COLOR = "#4a90d9"
CIRCLE_WEAK_OUTLINE = "#888888"


class MetronomeGUI(tk.Tk):
        def __init__(self):
                super().__init__()

                self.title("BPM Metronome")
                self.geometry("1024x900")
                self.minsize(1024, 900)

                self.style = ttk.Style(self)

                self.entries = load_entries_from_files()

                self.mode_var = tk.StringVar(value="interval")
                self.current_mode = self.mode_var.get()
                self.value_var = tk.StringVar(value="1.45")
                self.duration_var = tk.StringVar(value="5")

                self._syncing = False
                self.beep_vars = {}
                self.beep_preset_vars = {}
                self.beep_scale_vars = {}

                for which, _, defaults in BEEP_TYPES:
                        self.beep_vars[which] = {}
                        self.beep_preset_vars[which] = {}
                        self.beep_scale_vars[which] = {}

                        for setting_key, _, config_key, _, _ in BEEP_SETTINGS:
                                value = float(defaults[config_key])
                                self.beep_vars[which][setting_key] = tk.StringVar(value=format_float(value))
                                self.beep_scale_vars[which][setting_key] = tk.DoubleVar(value=value)
                                self.beep_preset_vars[which][setting_key] = tk.StringVar(
                                        value=self.get_preset_label_for_value(setting_key, value)
                                )

                self.beats_var = tk.StringVar(value=str(DEFAULT_BEATS))
                self.pattern = list(DEFAULT_PATTERN)
                self._circle_geometry = []

                self.click_profiles = load_click_profiles()
                self.click_profile_name_var = tk.StringVar()
                self.click_profile_var = tk.StringVar(value="Aucun profil")
                self.rename_var = tk.StringVar()
                self.rename_index = None

                self.build_ui()
                self.bind("<F2>", self.on_start_rename)
                self.bind("<Delete>", self.on_delete_key)
                self.protocol("WM_DELETE_WINDOW", self.on_close)
                self.refresh_list()
                self.draw_pattern()

        def build_ui(self):
                main = tk.Frame(self)
                main.pack(fill="both", expand=True, padx=12, pady=12)

                mode_frame = tk.LabelFrame(main, text="Mode")
                mode_frame.pack(fill="x")

                tk.Radiobutton(
                        mode_frame,
                        text="Intervalle en secondes",
                        variable=self.mode_var,
                        value="interval",
                        command=self.on_mode_change
                ).pack(side="left", padx=8, pady=8)

                tk.Radiobutton(
                        mode_frame,
                        text="BPM",
                        variable=self.mode_var,
                        value="bpm",
                        command=self.on_mode_change
                ).pack(side="left", padx=8, pady=8)

                input_frame = tk.Frame(main)
                input_frame.pack(fill="x", pady=10)

                tk.Label(input_frame, text="Valeur :").grid(row=0, column=0, sticky="w")
                tk.Entry(input_frame, textvariable=self.value_var, width=16).grid(row=0, column=1, padx=8)

                tk.Label(input_frame, text="Durée en minutes :").grid(row=0, column=2, sticky="w", padx=(20, 0))
                tk.Entry(input_frame, textvariable=self.duration_var, width=8).grid(row=0, column=3, padx=8)

                self.generate_button = tk.Button(
                        input_frame,
                        text="Sauvegarder WAV",
                        command=self.on_generate
                )
                self.generate_button.grid(row=0, column=4, padx=20)

                beeps_frame = tk.Frame(main)
                beeps_frame.pack(fill="x", pady=(0, 10))

                for index, (which, title, _) in enumerate(BEEP_TYPES):
                        editor = self.build_beep_editor(beeps_frame, which, title)
                        padx = (0, 6) if index == 0 else (6, 0)
                        editor.pack(side="left", fill="both", expand=True, padx=padx)

                self.build_pattern_section(main)
                self.build_profile_section(main)

                list_frame = tk.LabelFrame(main, text="Métronomes générés")
                list_frame.pack(fill="both", expand=True, pady=10)

                self.listbox = tk.Listbox(list_frame, height=10, exportselection=False)
                self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
                self.listbox.bind("<Double-Button-1>", lambda event: self.on_play())

                scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
                scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 8))
                self.listbox.config(yscrollcommand=scrollbar.set)

                action_frame = tk.Frame(main)
                action_frame.pack(fill="x")

                tk.Label(action_frame, text="Nouveau nom :").grid(row=0, column=0, sticky="w")
                self.rename_entry = tk.Entry(action_frame, textvariable=self.rename_var, width=30)
                self.rename_entry.grid(row=0, column=1, padx=8)
                self.rename_entry.bind("<Return>", lambda event: self.on_rename())

                tk.Button(action_frame, text="Renommer", command=self.on_rename).grid(row=0, column=2, padx=4)
                tk.Button(action_frame, text="Lancer / relancer", command=self.on_play).grid(row=0, column=3, padx=4)
                tk.Button(action_frame, text="Ouvrir dossier", command=self.on_open_folder).grid(row=0, column=4,
                                                                                                 padx=4)
                tk.Button(action_frame, text="Rafraîchir liste", command=self.on_refresh_list).grid(row=0, column=5,
                                                                                                    padx=4)
                tk.Button(action_frame, text="Supprimer", command=self.on_delete).grid(row=0, column=6, padx=4)

                status_bar = tk.Frame(main)
                status_bar.pack(fill="x", pady=(10, 0))

                self.status_var = tk.StringVar(value="Prêt.")
                tk.Label(status_bar, textvariable=self.status_var, anchor="w").pack(side="left")
                tk.Label(status_bar, text=f"v{APP_VERSION}", anchor="e", fg="#888888").pack(side="right")

        def build_beep_editor(self, parent, which, title):
                frame = tk.LabelFrame(parent, text=title)
                frame.grid_columnconfigure(1, weight=1)

                for row, (setting_key, label, _, vmin, vmax) in enumerate(BEEP_SETTINGS):
                        self.build_click_setting_row(frame, row, which, setting_key, label, vmin, vmax)

                ttk.Button(
                        frame,
                        text="Prévisualiser bip",
                        command=lambda w=which: self.on_preview_beep(w)
                ).grid(row=len(BEEP_SETTINGS), column=0, columnspan=3, sticky="w", padx=8, pady=(8, 8))

                return frame

        def build_pattern_section(self, parent):
                pattern_frame = tk.LabelFrame(parent, text="Temps par battement")
                pattern_frame.pack(fill="x", pady=(0, 10))

                top = tk.Frame(pattern_frame)
                top.pack(fill="x", padx=8, pady=(8, 4))

                tk.Label(top, text="Nombre de temps :").pack(side="left")

                beats_menu = tk.OptionMenu(
                        top,
                        self.beats_var,
                        *[str(n) for n in BEAT_CHOICES],
                        command=self.on_beats_change
                )
                beats_menu.config(width=4)
                beats_menu.pack(side="left", padx=8)

                tk.Label(
                        top,
                        text="(clique un rond pour basculer fort / faible)"
                ).pack(side="left", padx=8)

                tk.Button(
                        top,
                        text="Prévisualiser mesure",
                        command=self.on_preview_measure
                ).pack(side="right")

                canvas_width = CIRCLE_MARGIN * 2 + MAX_BEATS * (2 * CIRCLE_RADIUS + CIRCLE_GAP)
                self.pattern_canvas = tk.Canvas(
                        pattern_frame,
                        height=2 * CIRCLE_RADIUS + 20,
                        width=canvas_width,
                        highlightthickness=0
                )
                self.pattern_canvas.pack(anchor="w", padx=8, pady=(0, 8))
                self.pattern_canvas.bind("<Button-1>", self.on_pattern_click)

        def build_profile_section(self, parent):
                profile_frame = tk.LabelFrame(parent, text="Profils (bip fort + faible + pattern)")
                profile_frame.pack(fill="x", pady=(0, 10))

                row = tk.Frame(profile_frame)
                row.pack(fill="x", padx=8, pady=8)

                tk.Label(row, text="Nom :").pack(side="left")
                tk.Entry(row, textvariable=self.click_profile_name_var, width=22).pack(side="left", padx=8)

                self.click_profile_menu = tk.OptionMenu(row, self.click_profile_var, "")
                self.click_profile_menu.config(width=18)
                self.click_profile_menu.pack(side="left", padx=4)

                tk.Button(row, text="Sauvegarder profil", command=self.on_save_click_profile).pack(side="left", padx=4)
                tk.Button(row, text="Charger profil", command=self.on_load_click_profile).pack(side="left", padx=4)
                tk.Button(row, text="Supprimer profil", command=self.on_delete_click_profile).pack(side="left", padx=4)

                self.refresh_click_profile_menu()

        def build_click_setting_row(self, parent, row, which, setting_key, label, vmin, vmax):
                value_var = self.beep_vars[which][setting_key]
                preset_var = self.beep_preset_vars[which][setting_key]
                scale_var = self.beep_scale_vars[which][setting_key]

                ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)

                scale = ttk.Scale(
                        parent,
                        from_=vmin,
                        to=vmax,
                        orient="horizontal",
                        variable=scale_var,
                        command=lambda v, w=which, k=setting_key: self.on_scale_change(w, k, v)
                )
                scale.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

                entry = ttk.Entry(parent, textvariable=value_var, width=8)
                entry.grid(row=row, column=2, padx=(0, 8), pady=4)
                entry.bind("<Return>", lambda e, w=which, k=setting_key: self.on_value_commit(w, k))
                entry.bind("<FocusOut>", lambda e, w=which, k=setting_key: self.on_value_commit(w, k))

                presets = ttk.Frame(parent)
                presets.grid(row=row, column=3, sticky="w", padx=4, pady=4)

                for preset_label, preset_value in CLICK_SETTING_PRESETS[setting_key]:
                        ttk.Radiobutton(
                                presets,
                                text=f"{preset_label} ({format_float(preset_value)})",
                                variable=preset_var,
                                value=preset_label,
                                style="Toolbutton",
                                command=lambda w=which, k=setting_key, p=preset_value:
                                        self.apply_click_setting_preset(w, k, p)
                        ).pack(side="left", padx=1)

        def _set_beep_value(self, which, setting_key, value):
                """Met à jour ensemble le slider, le champ texte et le preset actif."""
                self._syncing = True

                try:
                        self.beep_scale_vars[which][setting_key].set(float(value))
                        self.beep_vars[which][setting_key].set(format_float(value))
                        self.beep_preset_vars[which][setting_key].set(
                                self.get_preset_label_for_value(setting_key, value)
                        )
                finally:
                        self._syncing = False

        def on_scale_change(self, which, setting_key, raw_value):
                if self._syncing:
                        return

                try:
                        value = float(raw_value)
                except (TypeError, ValueError):
                        return

                self._syncing = True

                try:
                        self.beep_vars[which][setting_key].set(format_float(value))
                        self.beep_preset_vars[which][setting_key].set(
                                self.get_preset_label_for_value(setting_key, value)
                        )
                finally:
                        self._syncing = False

        def on_value_commit(self, which, setting_key):
                if self._syncing:
                        return

                text = self.beep_vars[which][setting_key].get()

                try:
                        value = parse_float_expression(text)
                except ValueError:
                        return

                vmin, vmax = BEEP_RANGES[setting_key]
                clamped = max(vmin, min(vmax, value))
                self._set_beep_value(which, setting_key, clamped)

        def apply_click_setting_preset(self, which, setting_key, preset_value):
                self._set_beep_value(which, setting_key, preset_value)
                self.status_var.set("Preset du bip appliqué.")

        def get_preset_label_for_value(self, preset_key, value):
                for preset_label, preset_value in CLICK_SETTING_PRESETS[preset_key]:
                        if abs(preset_value - value) < 1e-9:
                                return preset_label

                return ""

        def collect_beep(self, which):
                variables = self.beep_vars[which]

                return parse_click_params(
                        variables["duration"].get(),
                        variables["frequency"].get(),
                        variables["brightness"].get(),
                        variables["decay"].get(),
                        variables["level"].get(),
                )

        # ---- Pattern (ronds fort / faible) ----

        def draw_pattern(self):
                canvas = self.pattern_canvas
                canvas.delete("all")
                self._circle_geometry = []

                y = CIRCLE_RADIUS + 10

                for i, is_strong in enumerate(self.pattern):
                        x = CIRCLE_MARGIN + CIRCLE_RADIUS + i * (2 * CIRCLE_RADIUS + CIRCLE_GAP)

                        fill = CIRCLE_STRONG_COLOR if is_strong else ""
                        outline = CIRCLE_STRONG_COLOR if is_strong else CIRCLE_WEAK_OUTLINE

                        canvas.create_oval(
                                x - CIRCLE_RADIUS, y - CIRCLE_RADIUS,
                                x + CIRCLE_RADIUS, y + CIRCLE_RADIUS,
                                fill=fill, outline=outline, width=2
                        )
                        canvas.create_text(
                                x, y,
                                text=str(i + 1),
                                fill="#ffffff" if is_strong else "#444444"
                        )

                        self._circle_geometry.append((x, y))

        def on_pattern_click(self, event):
                for i, (x, y) in enumerate(self._circle_geometry):
                        if (event.x - x) ** 2 + (event.y - y) ** 2 <= CIRCLE_RADIUS ** 2:
                                self.pattern[i] = not self.pattern[i]
                                self.draw_pattern()
                                self.status_var.set(
                                        f"Temps {i + 1} : {'fort' if self.pattern[i] else 'faible'}."
                                )
                                break

        def on_beats_change(self, value):
                try:
                        beats = int(value)
                except (TypeError, ValueError):
                        return

                beats = max(1, min(MAX_BEATS, beats))

                if beats > len(self.pattern):
                        self.pattern += [False] * (beats - len(self.pattern))
                else:
                        self.pattern = self.pattern[:beats]

                self.draw_pattern()
                self.status_var.set(f"{beats} temps par battement.")

        # ---- Profils ----

        def find_click_profile(self, name):
                return find_profile(self.click_profiles, name)

        def on_click_profile_selected(self, name):
                self.click_profile_var.set(name)
                self.click_profile_name_var.set(name)

        def refresh_click_profile_menu(self):
                menu = self.click_profile_menu["menu"]
                menu.delete(0, tk.END)

                profile_names = [profile["name"] for profile in self.click_profiles]

                if not profile_names:
                        self.click_profile_var.set("Aucun profil")
                        self.click_profile_name_var.set("")
                        menu.add_command(label="Aucun profil", command=lambda: self.click_profile_var.set("Aucun profil"))
                        return

                current_name = self.click_profile_var.get()

                if current_name not in profile_names:
                        current_name = profile_names[0]
                        self.click_profile_var.set(current_name)

                if not self.click_profile_name_var.get().strip():
                        self.click_profile_name_var.set(current_name)

                for profile_name in profile_names:
                        menu.add_command(
                                label=profile_name,
                                command=lambda name=profile_name: self.on_click_profile_selected(name)
                        )

        def apply_click_profile(self, profile):
                for which, _, _ in BEEP_TYPES:
                        beep = profile[which]

                        for setting_key, _, config_key, _, _ in BEEP_SETTINGS:
                                self._set_beep_value(which, setting_key, beep[config_key])

                self.beats_var.set(str(profile["beats"]))
                self.pattern = list(profile["pattern"])
                self.draw_pattern()

        def collect_profile_config(self):
                return {
                        "beats": len(self.pattern),
                        "pattern": list(self.pattern),
                        "strong": self.collect_beep("strong"),
                        "weak": self.collect_beep("weak"),
                }

        def on_save_click_profile(self):
                name = self.click_profile_name_var.get().strip()

                if not name:
                        messagebox.showinfo("Info", "Entre un nom de profil.")
                        return

                try:
                        config = self.collect_profile_config()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                existing_profile = self.find_click_profile(name)

                if existing_profile is not None:
                        confirmed = messagebox.askyesno(
                                "Remplacer le profil",
                                f"Le profil existe déjà.\n\nRemplacer : {existing_profile['name']} ?"
                        )

                        if not confirmed:
                                return

                        existing_profile.update(config)
                        existing_profile["name"] = name
                else:
                        self.click_profiles.append({"name": name, **config})

                self.click_profiles.sort(key=lambda profile: profile["name"].lower())
                save_click_profiles(self.click_profiles)
                self.click_profile_var.set(name)
                self.refresh_click_profile_menu()
                self.status_var.set(f"Profil sauvegardé : {name}")

        def on_load_click_profile(self):
                profile = self.find_click_profile(self.click_profile_var.get())

                if profile is None:
                        messagebox.showinfo("Info", "Sélectionne un profil.")
                        return

                self.apply_click_profile(profile)
                self.click_profile_name_var.set(profile["name"])
                self.status_var.set(f"Profil chargé : {profile['name']}")

        def on_delete_click_profile(self):
                profile = self.find_click_profile(self.click_profile_var.get())

                if profile is None:
                        messagebox.showinfo("Info", "Sélectionne un profil.")
                        return

                confirmed = messagebox.askyesno(
                        "Confirmer la suppression",
                        f"Supprimer ce profil ?\n\n{profile['name']}"
                )

                if not confirmed:
                        return

                deleted_name = profile["name"]
                self.click_profiles.remove(profile)
                save_click_profiles(self.click_profiles)
                self.click_profile_name_var.set("")
                self.refresh_click_profile_menu()
                self.status_var.set(f"Profil supprimé : {deleted_name}")

        def on_delete_key(self, event=None):
                if isinstance(self.focus_get(), tk.Entry):
                        return

                self.on_delete()

        def cleanup_preview_files(self):
                temp_dir = Path(tempfile.gettempdir())

                for path in temp_dir.glob("bpm-metronome-preview-*.wav"):
                        try:
                                path.unlink()
                        except Exception:
                                pass

        def on_close(self):
                self.cleanup_preview_files()
                self.destroy()

        def on_mode_change(self):
                new_mode = self.mode_var.get()

                if new_mode == self.current_mode:
                        return

                raw_value = self.value_var.get()

                try:
                        value = parse_float_expression(raw_value)

                        if value <= 0:
                                raise ValueError
                except ValueError:
                        self.current_mode = new_mode
                        self.status_var.set("Mode changé. Valeur non convertie car elle est invalide.")
                        return

                if self.current_mode == "interval" and new_mode == "bpm":
                        converted_value = 60 / value
                        unit = "BPM"
                else:
                        converted_value = 60 / value
                        unit = "s"

                self.value_var.set(format_float(converted_value, 9))
                self.current_mode = new_mode
                self.status_var.set(f"Valeur convertie en {unit}.")

        def parse_params(self):
                strong = self.collect_beep("strong")
                weak = self.collect_beep("weak")

                return parse_metronome_params(
                        self.mode_var.get(),
                        self.value_var.get(),
                        self.duration_var.get(),
                        strong,
                        weak,
                        list(self.pattern),
                )

        def temp_preview_path(self):
                return Path(tempfile.gettempdir()) / f"bpm-metronome-preview-{int(time.time() * 1000)}.wav"

        def on_preview_beep(self, which):
                try:
                        beep = self.collect_beep(which)
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                path = self.temp_preview_path()

                try:
                        generate_click_preview_wav(path, beep)
                        open_file(path)
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        self.status_var.set("Erreur pendant la prévisualisation.")
                        return

                self.status_var.set("Prévisualisation du bip lancée.")

        def on_preview_measure(self):
                try:
                        params = self.parse_params()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                path = self.temp_preview_path()

                try:
                        generate_measure_preview_wav(
                                path,
                                samples_between=params["samples_between"],
                                strong_beep=params["strong"],
                                weak_beep=params["weak"],
                                pattern=params["pattern"],
                                measures=2,
                        )
                        open_file(path)
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        self.status_var.set("Erreur pendant la prévisualisation de la mesure.")
                        return

                self.status_var.set("Prévisualisation de la mesure lancée (2 mesures).")

        def on_generate(self):
                try:
                        params = self.parse_params()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                cached = find_cached_entry(self.entries, params)

                if cached is not None:
                        self.status_var.set(f"Déjà généré : {cached['filename']}")
                        self.select_entry(cached)
                        return

                self.generate_button.config(state="disabled")
                self.status_var.set("Génération en cours...")

                thread = threading.Thread(
                        target=self.generate_worker,
                        args=(params,),
                        daemon=True
                )
                thread.start()

        def generate_worker(self, params):
                try:
                        entry = generate_metronome(params)
                        self.after(0, lambda: self.on_generate_done(entry))
                except Exception as e:
                        self.after(0, lambda err=e: self.on_generate_error(err))

        def on_generate_done(self, entry):
                self.entries.append(entry)
                save_db(self.entries)

                self.refresh_list()
                self.select_entry(entry)

                self.generate_button.config(state="normal")
                self.status_var.set(f"Généré : {entry['filename']}")

        def on_generate_error(self, error):
                self.generate_button.config(state="normal")
                messagebox.showerror("Erreur", str(error))
                self.status_var.set("Erreur pendant la génération.")

        def refresh_list(self):
                self.listbox.delete(0, tk.END)

                for entry in self.entries:
                        filename = entry.get("filename", "?")
                        bpm = entry.get("actual_bpm")
                        interval = entry.get("actual_interval_s")
                        duration_s = entry.get("duration_s")
                        duration_min = duration_s / 60 if duration_s is not None else None
                        pattern = entry.get("pattern")

                        bpm_text = format_float(bpm, 9) if bpm is not None else "?"
                        interval_text = format_float(interval, 9) if interval is not None else "?"
                        duration_text = format_float(duration_min, 3) if duration_min is not None else "?"

                        if isinstance(pattern, list) and pattern:
                                pattern_text = "".join("X" if b else "." for b in pattern)
                        else:
                                pattern_text = "?"

                        line = (
                                f"{filename}  |  "
                                f"{bpm_text} BPM  |  "
                                f"{interval_text} s  |  "
                                f"{duration_text} min  |  "
                                f"{pattern_text}"
                        )

                        self.listbox.insert(tk.END, line)

        def on_refresh_list(self):
                self.entries = load_entries_from_files()
                save_db(self.entries)
                self.refresh_list()
                self.status_var.set("Liste rafraîchie.")

        def get_selected_index(self):
                selection = self.listbox.curselection()

                if not selection:
                        messagebox.showinfo("Info", "Sélectionne un métronome dans la liste.")
                        return None

                return selection[0]

        def get_selected_entry(self):
                index = self.get_selected_index()

                if index is None:
                        return None

                return self.entries[index]

        def select_entry(self, entry):
                try:
                        index = self.entries.index(entry)
                except ValueError:
                        return

                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
                self.listbox.see(index)

        def on_start_rename(self, event=None):
                index = self.get_selected_index()

                if index is None:
                        return

                self.rename_index = index
                entry = self.entries[index]
                self.rename_var.set(entry["filename"])
                self.rename_entry.focus_set()
                self.rename_entry.selection_range(0, tk.END)
                self.status_var.set("Modifie le nom puis appuie sur Entrée pour renommer.")

        def on_rename(self):
                selection = self.listbox.curselection()
                index = selection[0] if selection else self.rename_index

                if index is None:
                        messagebox.showinfo("Info", "Sélectionne un métronome dans la liste.")
                        return

                if index < 0 or index >= len(self.entries):
                        self.rename_index = None
                        messagebox.showinfo("Info", "Sélectionne un métronome dans la liste.")
                        return

                entry = self.entries[index]

                old_path = OUT_DIR / entry["filename"]

                if not old_path.exists():
                        messagebox.showerror("Erreur", "Le fichier n'existe plus.")
                        return

                new_name = sanitize_filename(self.rename_var.get())
                new_path = OUT_DIR / new_name

                if new_path.exists():
                        messagebox.showerror("Erreur", "Un fichier avec ce nom existe déjà.")
                        return

                old_path.rename(new_path)

                entry["filename"] = new_path.name
                save_db(self.entries)

                self.refresh_list()
                self.listbox.selection_set(index)
                self.rename_index = index
                self.status_var.set(f"Renommé en : {new_path.name}")

        def on_play(self):
                entry = self.get_selected_entry()

                if entry is None:
                        return

                path = OUT_DIR / entry["filename"]

                if not path.exists():
                        messagebox.showerror("Erreur", "Le fichier n'existe plus.")
                        return

                open_file(path)
                self.status_var.set(f"Lancé : {entry['filename']}")

        def on_delete(self):
                index = self.get_selected_index()

                if index is None:
                        return

                entry = self.entries[index]
                filename = entry["filename"]
                path = OUT_DIR / filename

                confirmed = messagebox.askyesno(
                        "Confirmer la suppression",
                        f"Supprimer définitivement ce fichier ?\n\n{filename}"
                )

                if not confirmed:
                        return

                try:
                        if path.exists():
                                path.unlink()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                del self.entries[index]
                save_db(self.entries)
                self.refresh_list()

                if self.entries:
                        next_index = min(index, len(self.entries) - 1)
                        self.listbox.selection_set(next_index)

                self.status_var.set(f"Supprimé : {filename}")

        def on_open_folder(self):
                OUT_DIR.mkdir(exist_ok=True)
                open_file(OUT_DIR)
