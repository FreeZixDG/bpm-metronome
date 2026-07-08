import sys
import wave
from array import array

from features.audio.core import make_click
from features.shared.constants import SAMPLE_RATE


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
