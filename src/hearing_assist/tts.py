from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
from queue import Queue


class TextSpeaker:
    """Queue final captions for OS text-to-speech output."""

    def __init__(
        self,
        voice: str | None = None,
        rate: int = 0,
        volume: int = 100,
    ) -> None:
        self._voice = voice
        self._rate = max(-10, min(10, rate))
        self._volume = max(0, min(100, volume))
        self._queue: Queue[str | None] = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def speak(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            self._queue.put(cleaned)

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=10.0)

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                return
            try:
                speak_once(text, self._voice, self._rate, self._volume)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr, flush=True)


def speak_once(
    text: str,
    voice: str | None = None,
    rate: int = 0,
    volume: int = 100,
) -> None:
    if sys.platform != "win32":
        raise RuntimeError("TTS読み上げは現在 Windows の System.Speech のみ対応です。")

    script = _build_powershell_script(
        text=text,
        voice=voice,
        rate=max(-10, min(10, rate)),
        volume=max(0, min(100, volume)),
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"TTS読み上げに失敗しました: {detail}")


def _build_powershell_script(
    text: str,
    voice: str | None,
    rate: int,
    volume: int,
) -> str:
    text_json = json.dumps(text, ensure_ascii=False)
    voice_json = json.dumps(voice, ensure_ascii=False)
    return f"""
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Rate = {rate}
$speaker.Volume = {volume}
$voice = ConvertFrom-Json @'
{voice_json}
'@
if ($null -ne $voice -and $voice -ne '') {{
    $speaker.SelectVoice($voice)
}}
$text = ConvertFrom-Json @'
{text_json}
'@
$speaker.Speak($text)
$speaker.Dispose()
"""
