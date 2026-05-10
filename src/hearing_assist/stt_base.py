from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RecognitionResult:
    text: str
    is_final: bool


class Recognizer(Protocol):
    def accept_audio(self, pcm16: bytes) -> RecognitionResult | None:
        ...

    def flush(self) -> RecognitionResult | None:
        ...
