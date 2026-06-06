# LFM2.5-Audio-JP TTS API

`LiquidAI/LFM2.5-Audio-1.5B-JP` をTTSとして使うための最小FastAPIサーバーです。

## セットアップ

GPU環境を推奨します。CPUでも起動はできますが、デモ用途の待ち時間には向きません。

```powershell
cd C:\補聴器\-project\lfm_tts_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

CUDA版PyTorchが必要な場合は、環境に合わせてPyTorch公式手順で先に `torch` を入れてください。

## 起動

```powershell
uvicorn app:app --host 0.0.0.0 --port 8000
```

初回リクエスト時にモデルを読み込みます。デモ前に先に読み込む場合:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/warmup
```

## TTS実行

WAVを直接保存:

```powershell
$body = @{
  text = "本日はお忙しい中ありがとうございます。"
  response_format = "wav"
} | ConvertTo-Json

Invoke-WebRequest `
  -Method Post `
  -Uri http://localhost:8000/tts `
  -ContentType "application/json" `
  -Body $body `
  -OutFile .\tts_jp.wav
```

JSONでbase64音声を受け取る場合:

```powershell
$body = @{
  text = "本日はお忙しい中ありがとうございます。"
  response_format = "base64"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/tts `
  -ContentType "application/json" `
  -Body $body
```

## パラメータ

- `text`: 読み上げる日本語テキスト
- `max_new_tokens`: 生成上限。長文では増やします
- `audio_temperature`: 音声生成の揺らぎ
- `audio_top_k`: 音声生成候補数
- `response_format`: `wav` または `base64`

## 環境変数

- `LFM_TTS_HF_REPO`: 既定は `LiquidAI/LFM2.5-Audio-1.5B-JP`
- `LFM_TTS_DEVICE`: 既定はCUDAがあれば `cuda`、なければ `cpu`
- `LFM_TTS_DTYPE`: 既定は `bfloat16`。必要に応じて `float16` / `float32`
- `LFM_TTS_CORS_ORIGINS`: 既定は `*`

## スマホアプリから使う場合

同じLAN内のPCで起動して、スマホ側から `http://PCのIPアドレス:8000/tts` を呼びます。
インターネット越しの営業デモでは、RunPod / Modal / Hugging Face Spaces などに同じAPIを置く構成にしてください。

