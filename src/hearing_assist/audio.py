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
