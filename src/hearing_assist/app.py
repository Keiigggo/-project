from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .audio import (
    AudioInputError,
    MicrophoneStream,
    RingBuffer,
    VoiceEnhancer,
    replay_pcm16,
)
from .config import AppConfig
from .stt_base import Recognizer
from .stt_vosk import VoskRecognizer
from .stt_whisper_cpp import WhisperCppRecognizer
from .tts import TextSpeaker


def parse_args() -> AppConfig:
    parser = argparse.ArgumentParser(
        description="補聴支援プロトタイプ: マイク入力を日本語字幕化する"
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        required=True,
        help="STTモデルのディレクトリ/ファイルパス",
    )
    parser.add_argument("--backend", choices=["vosk", "whispercpp"], default="vosk")
    parser.add_argument("--sample-rate", type=int, default=16_000)
    parser.add_argument("--block-size", type=int, default=8_000)
    parser.add_argument("--buffer-seconds", type=int, default=10)
    parser.add_argument(
        "--transcript-path",
        type=Path,
        default=Path("transcripts/latest_transcript.txt"),
    )
    parser.add_argument(
        "--replay-on-stop",
        action="store_true",
        help="終了時に直前バッファを再生する",
    )
    parser.add_argument(
        "--whisper-cli-path",
        type=str,
        default="whisper-cli",
        help="whisper.cpp CLI実行ファイル名またはパス",
    )
    parser.add_argument(
        "--speak-final",
        action="store_true",
        help="確定字幕をOSの別音声で読み上げる",
    )
    parser.add_argument(
        "--tts-voice",
        type=str,
        default=None,
        help="読み上げに使うWindows音声名。例: Microsoft Haruka Desktop",
    )
    parser.add_argument("--tts-rate", type=int, default=0, help="読み上げ速度 -10..10")
    parser.add_argument("--tts-volume", type=int, default=100, help="読み上げ音量 0..100")

    args = parser.parse_args()
    return AppConfig(
        model_path=args.model_path,
        backend=args.backend,
        sample_rate=args.sample_rate,
        block_size=args.block_size,
        buffer_seconds=args.buffer_seconds,
        transcript_path=args.transcript_path,
        replay_on_stop=args.replay_on_stop,
        whisper_cli_path=args.whisper_cli_path,
        speak_final=args.speak_final,
        tts_voice=args.tts_voice,
        tts_rate=args.tts_rate,
        tts_volume=args.tts_volume,
    )


def ensure_output_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def make_recognizer(config: AppConfig) -> Recognizer:
    if config.backend == "vosk":
        return VoskRecognizer(config.model_path, config.sample_rate)
    return WhisperCppRecognizer(
        model_path=config.model_path,
        sample_rate=config.sample_rate,
        whisper_cli_path=config.whisper_cli_path,
    )


def run(config: AppConfig) -> int:
    ensure_output_path(config.transcript_path)

    try:
        recognizer = make_recognizer(config)
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    mic = MicrophoneStream(
        sample_rate=config.sample_rate,
        block_size=config.block_size,
        channels=config.channels,
    )
    ring = RingBuffer(config.buffer_samples)
    enhancer = VoiceEnhancer(config.sample_rate)
    speaker = (
        TextSpeaker(
            voice=config.tts_voice,
            rate=config.tts_rate,
            volume=config.tts_volume,
        )
        if config.speak_final
        else None
    )

    print(f"開始: Ctrl+C で停止。backend={config.backend}", flush=True)
    print(f"字幕は {config.transcript_path} に保存されます。", flush=True)
    if speaker is not None:
        print("確定字幕を読み上げます。", flush=True)

    try:
        mic.start()
    except AudioInputError as exc:
        if speaker is not None:
            speaker.close()
        print(str(exc), file=sys.stderr)
        return 2

    with config.transcript_path.open("w", encoding="utf-8") as fp:
        try:
            while True:
                chunk = mic.read(timeout=1.0)
                samples = np.frombuffer(chunk.pcm16, dtype=np.int16)
                enhanced_samples = enhancer.process(samples)
                ring.append(enhanced_samples)

                result = recognizer.accept_audio(chunk.pcm16)
                if result is None:
                    continue

                prefix = "[FINAL]" if result.is_final else "[PARTIAL]"
                line = f"{prefix} {result.text}"
                print(line, flush=True)
                if result.is_final:
                    fp.write(result.text + "\n")
                    fp.flush()
                    if speaker is not None:
                        speaker.speak(result.text)
        except KeyboardInterrupt:
            print("\n停止します。", flush=True)
        finally:
            mic.stop()

    tail = recognizer.flush()
    if tail is not None:
        print(f"[FINAL] {tail.text}")
        if speaker is not None:
            speaker.speak(tail.text)

    if speaker is not None:
        speaker.close()

    if config.replay_on_stop:
        print("直前バッファを再生します。", flush=True)
        replay_pcm16(ring.latest(), config.sample_rate)

    return 0


def main() -> None:
    config = parse_args()
    raise SystemExit(run(config))


if __name__ == "__main__":
    main()
