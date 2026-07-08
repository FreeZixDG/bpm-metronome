import sys
import wave
from array import array

from features.audio.core import make_click_from_config
from features.shared.constants import SAMPLE_RATE


def _clamp_sample(value):
        if value > 32767:
                return 32767
        if value < -32768:
                return -32768
        return value


def _mix_click(buffer, click, start):
        """Ajoute un clic dans un tampon en mémoire, avec limitation d'amplitude."""
        buffer_len = len(buffer)

        for i, sample in enumerate(click):
                j = start + i

                if j < 0:
                        continue
                if j >= buffer_len:
                        break

                buffer[j] = _clamp_sample(buffer[j] + sample)


def _write_wav(path, buffer):
        pcm = array("h", buffer)

        if sys.byteorder != "little":
                pcm.byteswap()

        with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(pcm.tobytes())


def generate_wav(path, duration_s, samples_between, strong_beep, weak_beep, pattern):
        """
        Génère un WAV en streaming, sans créer un énorme tableau audio complet en RAM.
        Le clic joué sur chaque temps dépend du pattern d'accents (fort / faible).
        """
        total_samples = int(duration_s * SAMPLE_RATE)
        strong = make_click_from_config(strong_beep)
        weak = make_click_from_config(weak_beep)
        max_click_len = max(len(strong), len(weak))
        n_beats = len(pattern)

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
                        click_index = max(0, (chunk_start - max_click_len) // samples_between)
                        click_pos = click_index * samples_between

                        while click_pos < chunk_end:
                                click = strong if pattern[click_index % n_beats] else weak
                                click_len = len(click)

                                overlap_start = max(chunk_start, click_pos)
                                overlap_end = min(chunk_end, click_pos + click_len)

                                if overlap_start < overlap_end:
                                        chunk_i = overlap_start - chunk_start
                                        click_i = overlap_start - click_pos
                                        length = overlap_end - overlap_start

                                        for j in range(length):
                                                chunk[chunk_i + j] = _clamp_sample(
                                                        chunk[chunk_i + j] + click[click_i + j]
                                                )

                                click_index += 1
                                click_pos = click_index * samples_between

                        pcm = array("h", chunk)

                        if sys.byteorder != "little":
                                pcm.byteswap()

                        wav.writeframes(pcm.tobytes())


def generate_click_preview_wav(path, beep):
        """Prévisualise un seul bip (trois répétitions rapprochées)."""
        click = make_click_from_config(beep)

        total_samples = int(1.5 * SAMPLE_RATE)
        samples_between = int(0.5 * SAMPLE_RATE)
        audio = [0] * total_samples

        for click_pos in range(0, total_samples, samples_between):
                _mix_click(audio, click, click_pos)

        _write_wav(path, audio)


def generate_measure_preview_wav(path, samples_between, strong_beep, weak_beep, pattern, measures=2):
        """Prévisualise le pattern complet, répété sur plusieurs mesures."""
        strong = make_click_from_config(strong_beep)
        weak = make_click_from_config(weak_beep)
        max_click_len = max(len(strong), len(weak))
        n_beats = len(pattern)

        beats_total = n_beats * measures
        tail = max_click_len + int(0.15 * SAMPLE_RATE)
        total_samples = max(0, beats_total - 1) * samples_between + tail
        audio = [0] * total_samples

        for i in range(beats_total):
                click = strong if pattern[i % n_beats] else weak
                _mix_click(audio, click, i * samples_between)

        _write_wav(path, audio)
