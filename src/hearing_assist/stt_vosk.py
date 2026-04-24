from __future__ import annotations

import json
from pathlib import Path

from vosk import KaldiRecognizer, Model

from .stt_base import RecognitionResult


class VoskRecognizer:
    def __init__(self, model_path: Path, sample_rate: int) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"Voskモデルが見つかりません: {model_path}"
            )
        self._model = Model(str(model_path))
        self._recognizer = KaldiRecognizer(self._model, sample_rate)
        self._recognizer.SetWords(True)

    def accept_audio(self, pcm16: bytes) -> RecognitionResult | None:
        has_final = self._recognizer.AcceptWaveform(pcm16)
        if has_final:
            payload = json.loads(self._recognizer.Result())
            text = payload.get("text", "").strip()
            if text:
                return RecognitionResult(text=text, is_final=True)
            return None

        payload = json.loads(self._recognizer.PartialResult())
        text = payload.get("partial", "").strip()
        if not text:
            return None
        return RecognitionResult(text=text, is_final=False)

    def flush(self) -> RecognitionResult | None:
        payload = json.loads(self._recognizer.FinalResult())
        text = payload.get("text", "").strip()
        if not text:
            return None
        return RecognitionResult(text=text, is_final=True)
