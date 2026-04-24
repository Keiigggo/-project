# hearing-assist（プロトタイプ）

日本語向けの**補聴支援アプリ試作**です。  
まずは「周囲音声をローカルで文字起こしする」最小実装から開始しています。

## 現在できること
- マイク入力の取得
- オフラインSTT（Vosk / whisper.cpp CLI）
- 部分結果 / 確定結果のコンソール表示（Vosk）
- 確定結果を `transcripts/latest_transcript.txt` に保存
- 終了時に直前バッファを再生（オプション）

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## バックエンド別モデル準備

### 1) Vosk（推奨・軽量）
1. Vosk公式の日本語モデルを取得（例: `vosk-model-small-ja-0.22`）
2. 展開して任意ディレクトリに配置

例:
```bash
mkdir -p models
# ダウンロードと展開は各自で実施
# models/vosk-model-small-ja-0.22/
```

### 2) whisper.cpp
1. whisper.cpp をビルドして `whisper-cli` を使える状態にする
2. GGUFモデルを配置（例: `models/ggml-base.bin` など）

## 実行

### Vosk
```bash
hearing-assist \
  --backend vosk \
  --model-path models/vosk-model-small-ja-0.22
```

### whisper.cpp
```bash
hearing-assist \
  --backend whispercpp \
  --model-path models/ggml-base.bin \
  --whisper-cli-path whisper-cli
```

### 終了時に直前10秒を再生する
```bash
hearing-assist \
  --backend vosk \
  --model-path models/vosk-model-small-ja-0.22 \
  --replay-on-stop
```

## まだ未実装（次ステップ）
- 常時UI（モバイル/デスクトップ）
- 辞書補正（駅名・人名など）
- WebRTC Audio Processing / RNNoise の前処理
- whisper.cpp の真のストリーミング化（現在は短い窓ごとの変換）

## ライセンス
- このリポジトリ: `LICENSE`
- 依存ライブラリのライセンスは各プロジェクトに従ってください。
