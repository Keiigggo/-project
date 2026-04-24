from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

STTBackend = Literal["vosk", "whispercpp"]


@dataclass(slots=True)
class AppConfig:
    model_path: Path
    sample_rate: int = 16_000
    block_size: int = 8_000
    channels: int = 1
    buffer_seconds: int = 10
    transcript_path: Path = Path("transcripts/latest_transcript.txt")
    backend: STTBackend = "vosk"
    replay_on_stop: bool = False
    whisper_cli_path: str = "whisper-cli"

    @property
    def buffer_samples(self) -> int:
        return self.sample_rate * self.buffer_seconds
