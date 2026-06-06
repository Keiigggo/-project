from __future__ import annotations

import base64
import io
import os
import threading
import time
from typing import Literal

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from liquid_audio import ChatState, LFM2AudioModel, LFM2AudioProcessor


HF_REPO = os.getenv("LFM_TTS_HF_REPO", "LiquidAI/LFM2.5-Audio-1.5B-JP")
DEVICE = os.getenv("LFM_TTS_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
DTYPE_NAME = os.getenv("LFM_TTS_DTYPE", "bfloat16")
SAMPLE_RATE = 24_000


def _dtype() -> torch.dtype:
    if DTYPE_NAME == "float16":
        return torch.float16
    if DTYPE_NAME == "float32":
        return torch.float32
    return torch.bfloat16


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    max_new_tokens: int = Field(512, ge=32, le=4096)
    audio_temperature: float = Field(0.8, ge=0.0, le=2.0)
    audio_top_k: int = Field(64, ge=1, le=512)
    response_format: Literal["wav", "base64"] = "wav"


class HealthResponse(BaseModel):
    status: Literal["ok"]
    repo: str
    device: str
    dtype: str
    model_loaded: bool


class Base64AudioResponse(BaseModel):
    sample_rate: int
    audio_base64: str
    elapsed_seconds: float


app = FastAPI(title="LFM2.5 Audio JP TTS API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("LFM_TTS_CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_load_lock = threading.Lock()
_generation_lock = threading.Lock()
_processor: LFM2AudioProcessor | None = None
_model: LFM2AudioModel | None = None


def load_model() -> tuple[LFM2AudioProcessor, LFM2AudioModel]:
    global _processor, _model
    if _processor is not None and _model is not None:
        return _processor, _model

    with _load_lock:
        if _processor is not None and _model is not None:
            return _processor, _model

        processor = LFM2AudioProcessor.from_pretrained(HF_REPO).eval()
        model = LFM2AudioModel.from_pretrained(HF_REPO).eval()

        if DEVICE != "cpu":
            model = model.to(device=DEVICE, dtype=_dtype())
        elif DTYPE_NAME == "float32":
            model = model.to(dtype=torch.float32)

        _processor = processor
        _model = model
        return processor, model


def synthesize(req: TtsRequest) -> tuple[bytes, float]:
    processor, model = load_model()
    started = time.perf_counter()

    chat = ChatState(processor)
    chat.new_turn("system")
    chat.add_text("Perform TTS in japanese.")
    chat.end_turn()

    chat.new_turn("user")
    chat.add_text(req.text)
    chat.end_turn()
    chat.new_turn("assistant")

    audio_out: list[torch.Tensor] = []
    with _generation_lock, torch.inference_mode():
        for token in model.generate_sequential(
            **chat,
            max_new_tokens=req.max_new_tokens,
            audio_temperature=req.audio_temperature,
            audio_top_k=req.audio_top_k,
        ):
            if token.numel() > 1:
                audio_out.append(token.detach().cpu())

    if len(audio_out) < 2:
        raise HTTPException(status_code=500, detail="No audio tokens were generated.")

    audio_codes = torch.stack(audio_out[:-1], 1).unsqueeze(0)
    waveform = processor.decode(audio_codes).cpu()[0].numpy()

    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, waveform, SAMPLE_RATE, format="WAV")
    return wav_buffer.getvalue(), time.perf_counter() - started


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        repo=HF_REPO,
        device=DEVICE,
        dtype=DTYPE_NAME,
        model_loaded=_processor is not None and _model is not None,
    )


@app.post("/warmup", response_model=HealthResponse)
def warmup() -> HealthResponse:
    load_model()
    return health()


@app.post("/tts")
def tts(req: TtsRequest) -> Response | Base64AudioResponse:
    wav_bytes, elapsed = synthesize(req)
    if req.response_format == "base64":
        return Base64AudioResponse(
            sample_rate=SAMPLE_RATE,
            audio_base64=base64.b64encode(wav_bytes).decode("ascii"),
            elapsed_seconds=elapsed,
        )

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-Elapsed-Seconds": f"{elapsed:.3f}"},
    )

