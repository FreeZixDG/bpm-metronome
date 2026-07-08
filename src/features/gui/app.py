import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from features.audio.usecase import generate_click_preview_wav
from features.click_profiles.core import find_profile
from features.click_profiles.repository import load_click_profiles, save_click_profiles
from features.metronomes.core import parse_click_params, parse_metronome_params
from features.metronomes.repository import load_entries_from_files, save_db
from features.metronomes.usecase import find_cached_entry, generate_metronome
from features.shared.constants import (
        CLICK_SETTING_PRESETS,
        DEFAULT_CLICK_BRIGHTNESS,
        DEFAULT_CLICK_DECAY,
        DEFAULT_CLICK_DURATION_S,
        DEFAULT_CLICK_FREQUENCY_HZ,
)
from features.shared.paths import OUT_DIR
from features.shared.utils import (
        format_float,
        open_file,
        parse_float_expression,
        sanitize_filename,
)


class MetronomeGUI(tk.Tk):
        def __init__(self):
                super().__init__()

                self.title("BPM Metronome")
                self.geometry("1100x700")

                self.entries = load_entries_from_files()

                self.mode_var = tk.StringVar(value="interval")
                self.current_mode = self.mode_var.get()
                self.value_var = tk.StringVar(value="1.45")
                self.duration_var = tk.StringVar(value="5")
                self.click_duration_var = tk.StringVar(value=format_float(DEFAULT_CLICK_DURATION_S))
                self.click_frequency_var = tk.StringVar(value=format_float(DEFAULT_CLICK_FREQUENCY_HZ))
                self.click_brightness_var = tk.StringVar(value=format_float(DEFAULT_CLICK_BRIGHTNESS))
                self.click_decay_var = tk.StringVar(value=format_float(DEFAULT_CLICK_DECAY))
                self.click_duration_preset_var = tk.StringVar(value="Moyen")
                self.click_frequency_preset_var = tk.StringVar(value="Moyen")
                self.click_brightness_preset_var = tk.StringVar(value="Moyenne")
                self.click_decay_preset_var = tk.StringVar(value="Moyen")
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

                sound_frame = tk.LabelFrame(main, text="Son du bip")
                sound_frame.pack(fill="x", pady=(0, 10))

                self.build_click_setting_row(
                        sound_frame, 0, "Durée du bip (s) :", self.click_duration_var,
                        self.click_duration_preset_var, "duration"
                )
                self.build_click_setting_row(
                        sound_frame, 1, "Fréquence (Hz) :", self.click_frequency_var,
                        self.click_frequency_preset_var, "frequency"
                )
                self.build_click_setting_row(
                        sound_frame, 2, "Brillance :", self.click_brightness_var,
                        self.click_brightness_preset_var, "brightness"
                )
                self.build_click_setting_row(
                        sound_frame, 3, "Decay :", self.click_decay_var,
                        self.click_decay_preset_var, "decay"
                )
                tk.Button(
                        sound_frame,
                        text="Prévisualiser bip",
                        command=self.on_preview_click
                ).grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

                profile_frame = tk.Frame(sound_frame)
                profile_frame.grid(row=5, column=0, columnspan=6, sticky="w", padx=8, pady=(4, 8))

                tk.Label(profile_frame, text="Profil :").pack(side="left")
                tk.Entry(profile_frame, textvariable=self.click_profile_name_var, width=22).pack(side="left", padx=8)

                self.click_profile_menu = tk.OptionMenu(profile_frame, self.click_profile_var, "")
                self.click_profile_menu.config(width=18)
                self.click_profile_menu.pack(side="left", padx=4)

                tk.Button(
                        profile_frame,
                        text="Sauvegarder profil",
                        command=self.on_save_click_profile
                ).pack(side="left", padx=4)
                tk.Button(
                        profile_frame,
                        text="Charger profil",
                        command=self.on_load_click_profile
                ).pack(side="left", padx=4)
                tk.Button(
                        profile_frame,
                        text="Supprimer profil",
                        command=self.on_delete_click_profile
                ).pack(side="left", padx=4)
                self.refresh_click_profile_menu()

                list_frame = tk.LabelFrame(main, text="Métronomes générés")
                list_frame.pack(fill="both", expand=True, pady=10)

                self.listbox = tk.Listbox(list_frame, height=12, exportselection=False)
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

                self.status_var = tk.StringVar(value="Prêt.")
                tk.Label(main, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(10, 0))

        def build_click_setting_row(self, parent, row, label, value_var, preset_var, preset_key):
                tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
                tk.Entry(parent, textvariable=value_var, width=10).grid(row=row, column=1, padx=8, pady=4)

                for i, (preset_label, preset_value) in enumerate(CLICK_SETTING_PRESETS[preset_key]):
                        tk.Radiobutton(
                                parent,
                                text=f"{preset_label} ({format_float(preset_value)})",
                                variable=preset_var,
                                value=preset_label,
                                command=lambda v=value_var, p=preset_value: self.apply_click_setting_preset(v, p)
                        ).grid(row=row, column=2 + i, sticky="w", padx=4, pady=4)

        def apply_click_setting_preset(self, value_var, preset_value):
                value_var.set(format_float(preset_value))
                self.status_var.set("Preset du bip appliqué.")

        def get_preset_label_for_value(self, preset_key, value):
                for preset_label, preset_value in CLICK_SETTING_PRESETS[preset_key]:
                        if abs(preset_value - value) < 1e-9:
                                return preset_label

                return ""

        def update_click_preset_vars(self, click_params):
                self.click_duration_preset_var.set(
                        self.get_preset_label_for_value("duration", click_params["click_duration_s"])
                )
                self.click_frequency_preset_var.set(
                        self.get_preset_label_for_value("frequency", click_params["click_frequency_hz"])
                )
                self.click_brightness_preset_var.set(
                        self.get_preset_label_for_value("brightness", click_params["click_brightness"])
                )
                self.click_decay_preset_var.set(
                        self.get_preset_label_for_value("decay", click_params["click_decay"])
                )

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
                self.click_duration_var.set(format_float(profile["click_duration_s"]))
                self.click_frequency_var.set(format_float(profile["click_frequency_hz"]))
                self.click_brightness_var.set(format_float(profile["click_brightness"]))
                self.click_decay_var.set(format_float(profile["click_decay"]))
                self.update_click_preset_vars(profile)

        def on_save_click_profile(self):
                name = self.click_profile_name_var.get().strip()

                if not name:
                        messagebox.showinfo("Info", "Entre un nom de profil.")
                        return

                try:
                        click_params = self.parse_click_params()
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

                        existing_profile.update(click_params)
                        existing_profile["name"] = name
                else:
                        self.click_profiles.append({
                                "name": name,
                                **click_params,
                        })

                self.click_profiles.sort(key=lambda profile: profile["name"].lower())
                save_click_profiles(self.click_profiles)
                self.click_profile_var.set(name)
                self.refresh_click_profile_menu()
                self.status_var.set(f"Profil de bip sauvegardé : {name}")

        def on_load_click_profile(self):
                profile = self.find_click_profile(self.click_profile_var.get())

                if profile is None:
                        messagebox.showinfo("Info", "Sélectionne un profil de bip.")
                        return

                self.apply_click_profile(profile)
                self.click_profile_name_var.set(profile["name"])
                self.status_var.set(f"Profil de bip chargé : {profile['name']}")

        def on_delete_click_profile(self):
                profile = self.find_click_profile(self.click_profile_var.get())

                if profile is None:
                        messagebox.showinfo("Info", "Sélectionne un profil de bip.")
                        return

                confirmed = messagebox.askyesno(
                        "Confirmer la suppression",
                        f"Supprimer ce profil de bip ?\n\n{profile['name']}"
                )

                if not confirmed:
                        return

                deleted_name = profile["name"]
                self.click_profiles.remove(profile)
                save_click_profiles(self.click_profiles)
                self.click_profile_name_var.set("")
                self.refresh_click_profile_menu()
                self.status_var.set(f"Profil de bip supprimé : {deleted_name}")

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

        def parse_click_params(self):
                return parse_click_params(
                        self.click_duration_var.get(),
                        self.click_frequency_var.get(),
                        self.click_brightness_var.get(),
                        self.click_decay_var.get(),
                )

        def parse_params(self):
                click_params = self.parse_click_params()

                return parse_metronome_params(
                        self.mode_var.get(),
                        self.value_var.get(),
                        self.duration_var.get(),
                        click_params,
                )

        def on_preview_click(self):
                try:
                        click_params = self.parse_click_params()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                path = Path(tempfile.gettempdir()) / f"bpm-metronome-preview-{int(time.time() * 1000)}.wav"

                try:
                        generate_click_preview_wav(path, click_params)
                        open_file(path)
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        self.status_var.set("Erreur pendant la prévisualisation.")
                        return

                self.status_var.set("Prévisualisation temporaire lancée. Clique sur Sauvegarder WAV pour garder ce son.")

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
                        samples = entry.get("samples_between")

                        bpm_text = format_float(bpm, 9) if bpm is not None else "?"
                        interval_text = format_float(interval, 9) if interval is not None else "?"
                        duration_text = format_float(duration_min, 3) if duration_min is not None else "?"
                        samples_text = samples if samples is not None else "?"

                        line = (
                                f"{filename}  |  "
                                f"{bpm_text} BPM  |  "
                                f"{interval_text} s  |  "
                                f"{duration_text} min  |  "
                                f"{samples_text} samples"
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
