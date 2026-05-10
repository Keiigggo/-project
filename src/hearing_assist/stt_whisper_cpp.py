from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from .stt_base import RecognitionResult


class WhisperCppRecognizer:
    """Minimal adapter for whisper.cpp CLI.

    This is not low-latency streaming yet. It transcribes buffered chunks every
    `transcribe_window_seconds` and returns them as final results.
    """

    def __init__(
        self,
        model_path: Path,
        sample_rate: int,
        transcribe_window_seconds: int = 4,
        whisper_cli_path: str = "whisper-cli",
    ) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"whisper.cppモデルが見つかりません: {model_path}")
        if shutil.which(whisper_cli_path) is None:
            raise FileNotFoundError(
                f"{whisper_cli_path} が見つかりません。whisper.cppをインストールしてください。"
            )

        self._model_path = model_path
        self._sample_rate = sample_rate
        self._window_bytes = sample_rate * transcribe_window_seconds * 2
        self._whisper_cli_path = whisper_cli_path
        self._buffer = bytearray()

    def accept_audio(self, pcm16: bytes) -> RecognitionResult | None:
        self._buffer.extend(pcm16)
        if len(self._buffer) < self._window_bytes:
            return None
        chunk = bytes(self._buffer)
        self._buffer.clear()
        text = self._transcribe_chunk(chunk)
        if not text:
            return None
        return RecognitionResult(text=text, is_final=True)

    def flush(self) -> RecognitionResult | None:
        if not self._buffer:
            return None
        chunk = bytes(self._buffer)
        self._buffer.clear()
        text = self._transcribe_chunk(chunk)
        if not text:
            return None
        return RecognitionResult(text=text, is_final=True)

    def _transcribe_chunk(self, pcm16: bytes) -> str:
        samples = np.frombuffer(pcm16, dtype=np.int16)
        with tempfile.TemporaryDirectory(prefix="hearing-assist-") as td:
            tmp_dir = Path(td)
            wav_path = tmp_dir / "chunk.wav"
            out_prefix = tmp_dir / "result"

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._sample_rate)
                wf.writeframes(samples.tobytes())

            cmd = [
                self._whisper_cli_path,
                "-m",
                str(self._model_path),
                "-f",
                str(wav_path),
                "-otxt",
                "-of",
                str(out_prefix),
                "-l",
                "ja",
                "--no-timestamps",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                stderr = proc.stderr.strip()
                raise RuntimeError(f"whisper.cpp実行失敗: {stderr}")

            txt_path = out_prefix.with_suffix(".txt")
            if not txt_path.exists():
                return ""
            return txt_path.read_text(encoding="utf-8").strip()
