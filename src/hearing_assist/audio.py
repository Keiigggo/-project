from __future__ import annotations

import queue
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


class AudioInputError(RuntimeError):
    """Raised when microphone input cannot be started."""


@dataclass
class AudioChunk:
    pcm16: bytes


class RingBuffer:
    """Simple mono PCM16 ring buffer for replay feature."""

    def __init__(self, max_samples: int) -> None:
        self._max_samples = max_samples
        self._buffer = np.zeros(max_samples, dtype=np.int16)
        self._write_index = 0
        self._filled = False

    def append(self, samples: np.ndarray) -> None:
        if samples.dtype != np.int16:
            raise ValueError("samples must be int16")
        n = len(samples)
        if n >= self._max_samples:
            self._buffer[:] = samples[-self._max_samples :]
            self._write_index = 0
            self._filled = True
            return

        end = self._write_index + n
        if end <= self._max_samples:
            self._buffer[self._write_index : end] = samples
        else:
            first = self._max_samples - self._write_index
            self._buffer[self._write_index :] = samples[:first]
            self._buffer[: end % self._max_samples] = samples[first:]
        self._write_index = end % self._max_samples
        if end >= self._max_samples:
            self._filled = True

    def latest(self) -> np.ndarray:
        if not self._filled:
            return self._buffer[: self._write_index].copy()
        return np.concatenate(
            [self._buffer[self._write_index :], self._buffer[: self._write_index]]
        )


class VoiceEnhancer:
    """Frequency-domain enhancer for replay audio.

    The recognizer still receives raw microphone audio. This enhancer is for
    listen-back output: reduce low-frequency rumble and stationary noise while
    giving the speech band more weight.
    """

    def __init__(
        self,
        sample_rate: int,
        voice_low_hz: float = 300.0,
        voice_high_hz: float = 4_000.0,
        voice_gain: float = 1.7,
        noise_reduction: float = 0.65,
    ) -> None:
        self._sample_rate = sample_rate
        self._voice_low_hz = voice_low_hz
        self._voice_high_hz = voice_high_hz
        self._voice_gain = voice_gain
        self._noise_reduction = noise_reduction
        self._noise_floor: np.ndarray | None = None
        self._freqs: np.ndarray | None = None
        self._band_weights: np.ndarray | None = None

    def process(self, samples: np.ndarray) -> np.ndarray:
        if samples.dtype != np.int16:
            raise ValueError("samples must be int16")
        if samples.size == 0:
            return samples.copy()

        float_samples = samples.astype(np.float32)
        float_samples -= float(np.mean(float_samples))

        spectrum = np.fft.rfft(float_samples)
        magnitudes = np.abs(spectrum)
        self._ensure_frequency_tables(samples.size)

        if self._noise_floor is None or self._noise_floor.shape != magnitudes.shape:
            self._noise_floor = magnitudes * 0.35
        else:
            below_floor = magnitudes < self._noise_floor
            self._noise_floor[below_floor] = (
                0.80 * self._noise_floor[below_floor] + 0.20 * magnitudes[below_floor]
            )
            self._noise_floor[~below_floor] = (
                0.995 * self._noise_floor[~below_floor]
                + 0.005 * magnitudes[~below_floor]
            )

        assert self._band_weights is not None
        assert self._noise_floor is not None

        noise_ratio = np.clip(self._noise_floor / (magnitudes + 1.0), 0.0, 1.0)
        noise_gate = 1.0 - self._noise_reduction * noise_ratio
        enhanced_spectrum = spectrum * self._band_weights * noise_gate

        enhanced = np.fft.irfft(enhanced_spectrum, n=samples.size).astype(np.float32)
        return _float_to_pcm16(enhanced)

    def _ensure_frequency_tables(self, sample_count: int) -> None:
        expected_count = sample_count // 2 + 1
        if self._freqs is not None and self._freqs.size == expected_count:
            return

        freqs = np.fft.rfftfreq(sample_count, d=1.0 / self._sample_rate)
        weights = np.full_like(freqs, 0.45, dtype=np.float32)

        weights[freqs < 80.0] = 0.05

        low_transition = (freqs >= 80.0) & (freqs < self._voice_low_hz)
        weights[low_transition] = np.interp(
            freqs[low_transition],
            [80.0, self._voice_low_hz],
            [0.12, 1.0],
        )

        voice_band = (freqs >= self._voice_low_hz) & (freqs <= self._voice_high_hz)
        weights[voice_band] = self._voice_gain

        high_transition = (freqs > self._voice_high_hz) & (freqs <= 7_000.0)
        weights[high_transition] = np.interp(
            freqs[high_transition],
            [self._voice_high_hz, 7_000.0],
            [0.9, 0.30],
        )

        weights[freqs > 7_000.0] = 0.20

        self._freqs = freqs
        self._band_weights = weights


class MicrophoneStream:
    def __init__(self, sample_rate: int, block_size: int, channels: int = 1) -> None:
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._channels = channels
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=32)
        self._stream: sd.RawInputStream | None = None

    def _callback(self, indata: bytes, frames: int, time, status) -> None:  # type: ignore[override]
        _ = (frames, time)
        if status:
            # Drop status handling in first iteration to keep callback realtime-safe.
            pass
        try:
            self._queue.put_nowait(AudioChunk(pcm16=bytes(indata)))
        except queue.Full:
            # Drop frames instead of blocking callback thread.
            pass

    def start(self) -> None:
        try:
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                blocksize=self._block_size,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001
            raise AudioInputError(f"マイク入力を開始できませんでした: {exc}") from exc

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: float = 1.0) -> AudioChunk:
        return self._queue.get(timeout=timeout)


def replay_pcm16(samples: np.ndarray, sample_rate: int) -> None:
    if samples.size == 0:
        return
    sd.play(samples.astype(np.int16), sample_rate)
    sd.wait()


def _float_to_pcm16(samples: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > 32_000.0:
        samples = samples * (32_000.0 / peak)
    return np.clip(samples, -32_768, 32_767).astype(np.int16)
