import ast
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import wave
from array import array
from pathlib import Path
from tkinter import messagebox

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

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "metros"
DB_FILE = OUT_DIR / "index.json"


# =========================
# UTILS
# =========================

def format_float(x, max_decimals=6):
        s = f"{x:.{max_decimals}f}"
        return s.rstrip("0").rstrip(".")


def parse_float_expression(text):
        text = text.replace(",", ".").strip()

        if not text:
                raise ValueError("La valeur est vide.")

        try:
                tree = ast.parse(text, mode="eval")
        except SyntaxError:
                raise ValueError("Expression numérique invalide.")

        def eval_node(node):
                if isinstance(node, ast.Expression):
                        return eval_node(node.body)

                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return float(node.value)

                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                        value = eval_node(node.operand)
                        return value if isinstance(node.op, ast.UAdd) else -value

                if isinstance(node, ast.BinOp):
                        left = eval_node(node.left)
                        right = eval_node(node.right)

                        if isinstance(node.op, ast.Add):
                                return left + right
                        if isinstance(node.op, ast.Sub):
                                return left - right
                        if isinstance(node.op, ast.Mult):
                                return left * right
                        if isinstance(node.op, ast.Div):
                                return left / right

                raise ValueError("Seuls les nombres et les opérations +, -, *, / sont acceptés.")

        try:
                value = eval_node(tree)
        except ZeroDivisionError:
                raise ValueError("Division par zéro.")

        if not math.isfinite(value):
                raise ValueError("Le résultat doit être un nombre fini.")

        return value


def sanitize_filename(name):
        invalid = '<>:"/\\|?*'
        for c in invalid:
                name = name.replace(c, "_")

        name = name.strip()

        if not name:
                name = "metronome.wav"

        if not name.lower().endswith(".wav"):
                name += ".wav"

        return name


def default_filename_from_bpm(bpm):
        OUT_DIR.mkdir(exist_ok=True)

        n = 1
        while True:
                filename = f"bpm-{n:03d}.wav"
                if not (OUT_DIR / filename).exists():
                        return filename
                n += 1


def load_db():
        OUT_DIR.mkdir(exist_ok=True)

        if not DB_FILE.exists():
                return []

        try:
                with DB_FILE.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                if isinstance(data, list):
                        return data

                return []
        except Exception:
                return []


def save_db(entries):
        OUT_DIR.mkdir(exist_ok=True)

        with DB_FILE.open("w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)


def load_entries_from_files():
        OUT_DIR.mkdir(exist_ok=True)

        db_entries = load_db()
        entries_by_filename = {
                entry.get("filename"): entry
                for entry in db_entries
                if isinstance(entry, dict) and entry.get("filename")
        }

        entries = []

        for path in sorted(OUT_DIR.iterdir(), key=lambda p: p.name.lower()):
                if not path.is_file() or path.suffix.lower() != ".wav":
                        continue

                entry = dict(entries_by_filename.get(path.name, {}))
                entry["filename"] = path.name
                entry.setdefault("created_at", path.stat().st_mtime)
                entries.append(entry)

        return entries


def unique_path(filename):
        filename = sanitize_filename(filename)
        path = OUT_DIR / filename

        if not path.exists():
                return path

        stem = path.stem
        suffix = path.suffix

        n = 2
        while True:
                candidate = OUT_DIR / f"{stem}_{n}{suffix}"
                if not candidate.exists():
                        return candidate
                n += 1


def open_file(path):
        path = Path(path)

        if sys.platform.startswith("win"):
                os.startfile(str(path))
        elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
        else:
                subprocess.Popen(["xdg-open", str(path)])


# =========================
# AUDIO
# =========================

def make_click(duration_s, frequency_hz, brightness, decay):
        """
        Crée le clic avec les réglages demandés.
        Ensuite, on le recopie dans le WAV aux bons endroits.
        """
        click_samples = int(duration_s * SAMPLE_RATE)
        click = []

        for n in range(click_samples):
                t = n / SAMPLE_RATE

                envelope = math.exp(-t * decay)

                value = envelope * (
                            CLICK_MAIN_LEVEL * math.sin(2 * math.pi * frequency_hz * t)
                            + brightness * math.sin(2 * math.pi * frequency_hz * 2 * t)
                )

                # Gain volontairement inférieur à 1 pour éviter le clipping
                value *= CLICK_GAIN

                sample = int(max(-1.0, min(1.0, value)) * 32767)
                click.append(sample)

        return click


def generate_wav(path, duration_s, samples_between, click_params):
        """
        Génère un WAV en streaming, sans créer un énorme tableau audio complet en RAM.
        """
        total_samples = int(duration_s * SAMPLE_RATE)
        click = make_click(
                duration_s=click_params["click_duration_s"],
                frequency_hz=click_params["click_frequency_hz"],
                brightness=click_params["click_brightness"],
                decay=click_params["click_decay"],
        )
        click_len = len(click)

        chunk_size = SAMPLE_RATE  # 1 seconde par chunk

        with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)

                for chunk_start in range(0, total_samples, chunk_size):
                        chunk_len = min(chunk_size, total_samples - chunk_start)
                        chunk_end = chunk_start + chunk_len

                        chunk = [0] * chunk_len

                        # Premier clic qui peut toucher ce chunk
                        first_click_index = max(0, (chunk_start - click_len) // samples_between)
                        click_pos = first_click_index * samples_between

                        while click_pos < chunk_end:
                                overlap_start = max(chunk_start, click_pos)
                                overlap_end = min(chunk_end, click_pos + click_len)

                                if overlap_start < overlap_end:
                                        chunk_i = overlap_start - chunk_start
                                        click_i = overlap_start - click_pos
                                        length = overlap_end - overlap_start

                                        for j in range(length):
                                                v = chunk[chunk_i + j] + click[click_i + j]

                                                if v > 32767:
                                                        v = 32767
                                                elif v < -32768:
                                                        v = -32768

                                                chunk[chunk_i + j] = v

                                click_pos += samples_between

                        pcm = array("h", chunk)

                        if sys.byteorder != "little":
                                pcm.byteswap()

                        wav.writeframes(pcm.tobytes())


def generate_click_preview_wav(path, click_params):
        click = make_click(
                duration_s=click_params["click_duration_s"],
                frequency_hz=click_params["click_frequency_hz"],
                brightness=click_params["click_brightness"],
                decay=click_params["click_decay"],
        )

        total_samples = int(1.5 * SAMPLE_RATE)
        samples_between = int(0.5 * SAMPLE_RATE)
        click_len = len(click)
        audio = [0] * total_samples

        for click_pos in range(0, total_samples, samples_between):
                for i, sample in enumerate(click):
                        audio_i = click_pos + i

                        if audio_i >= total_samples:
                                break

                        v = audio[audio_i] + sample

                        if v > 32767:
                                v = 32767
                        elif v < -32768:
                                v = -32768

                        audio[audio_i] = v

        pcm = array("h", audio)

        if sys.byteorder != "little":
                pcm.byteswap()

        with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(pcm.tobytes())


# =========================
# GUI
# =========================

class MetronomeGUI(tk.Tk):
        def __init__(self):
                super().__init__()

                self.title("Métronome WAV précis")
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

        def on_delete_key(self, event=None):
                if isinstance(self.focus_get(), tk.Entry):
                        return

                self.on_delete()

        def cleanup_preview_files(self):
                temp_dir = Path(tempfile.gettempdir())

                for path in temp_dir.glob("bnm-metronome-preview-*.wav"):
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
                click_duration_s = parse_float_expression(self.click_duration_var.get())
                click_frequency_hz = parse_float_expression(self.click_frequency_var.get())
                click_brightness = parse_float_expression(self.click_brightness_var.get())
                click_decay = parse_float_expression(self.click_decay_var.get())

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

                return {
                        "click_duration_s": click_duration_s,
                        "click_frequency_hz": click_frequency_hz,
                        "click_brightness": click_brightness,
                        "click_decay": click_decay,
                }

        def parse_params(self):
                raw_value = self.value_var.get()
                raw_duration = self.duration_var.get()

                value = parse_float_expression(raw_value)
                duration_min = parse_float_expression(raw_duration)
                click_params = self.parse_click_params()

                if value <= 0:
                        raise ValueError("La valeur doit être positive.")

                if duration_min <= 0:
                        raise ValueError("La durée doit être positive.")

                duration_s = duration_min * 60

                mode = self.mode_var.get()

                if mode == "bpm":
                        requested_bpm = value
                        requested_interval_s = 60 / requested_bpm
                else:
                        requested_interval_s = value
                        requested_bpm = 60 / requested_interval_s

                samples_between = round(requested_interval_s * SAMPLE_RATE)

                if samples_between <= 0:
                        raise ValueError("Intervalle trop court.")

                # Timing réellement représenté dans le WAV
                actual_interval_s = samples_between / SAMPLE_RATE
                actual_bpm = 60 / actual_interval_s

                return {
                        "mode": mode,
                        "requested_bpm": requested_bpm,
                        "requested_interval_s": requested_interval_s,
                        "actual_bpm": actual_bpm,
                        "actual_interval_s": actual_interval_s,
                        "samples_between": samples_between,
                        "duration_s": duration_s,
                        **click_params,
                }

        def on_preview_click(self):
                try:
                        click_params = self.parse_click_params()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                path = Path(tempfile.gettempdir()) / f"bpm-metronome-preview-{int(time.time() * 1000)}.wav"
                print(path)
                try:
                        generate_click_preview_wav(path, click_params)
                        open_file(path)
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        self.status_var.set("Erreur pendant la prévisualisation.")
                        return

                self.status_var.set("Prévisualisation temporaire lancée. Clique sur Sauvegarder WAV pour garder ce son.")

        def find_cached_entry(self, params):
                for entry in self.entries:
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

        def on_generate(self):
                try:
                        params = self.parse_params()
                except Exception as e:
                        messagebox.showerror("Erreur", str(e))
                        return

                cached = self.find_cached_entry(params)

                if cached is not None:
                        self.status_var.set(f"Déjà généré : {cached['filename']}")
                        self.select_entry(cached)
                        return

                filename = default_filename_from_bpm(params["requested_bpm"])
                path = unique_path(filename)

                self.generate_button.config(state="disabled")
                self.status_var.set("Génération en cours...")

                thread = threading.Thread(
                        target=self.generate_worker,
                        args=(path, params),
                        daemon=True
                )
                thread.start()

        def generate_worker(self, path, params):
                try:
                        generate_wav(
                                path=path,
                                duration_s=params["duration_s"],
                                samples_between=params["samples_between"],
                                click_params=params,
                        )

                        entry = {
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


if __name__ == "__main__":
        app = MetronomeGUI()
        app.mainloop()
