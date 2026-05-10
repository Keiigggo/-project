# 補聴支援アプリ設計メモ（日本向け・無料運用優先版）

更新日: 2026-04-24

## 0. 目的（今回の方針）
- **維持費を極力ゼロにする**（従量課金クラウドSTTを前提にしない）
- **日本語利用を最優先**
- 周囲音声を「取り込み → 字幕化 → 聞き直し」できる実用アプリを目指す

---

## 1. 結論（先に）

### 推奨構成（無料運用）
1. STT: **whisper.cpp**（第一候補）
2. 端末スペックが低い端末向け代替: **Vosk**
3. 前処理: **WebRTC Audio Processing** + 必要なら **RNNoise**
4. 再提示: 
   - A. 字幕表示
   - B. 整音した原音の再生
   - C. （任意）ローカルTTS再読み上げ

> これで「月額API費用なし」の構成にできる。

---

## 2. 無料で使えるSTT候補（日本語対応前提）

## A. whisper.cpp（最有力）
- OSS / MITライセンス
- OpenAI Whisperモデルをローカル実行できるC/C++実装
- iOS / Android / Desktopまで横展開しやすい
- モデルサイズを下げれば実時間に近い処理が可能

**向くケース**
- 日本語精度を優先したい
- サーバ費用をかけたくない
- オフライン動作を必須にしたい

## B. Vosk
- OSS / Apache-2.0
- オフライン対応、軽量モデルがあり低スペック端末に有利
- ストリーミングAPIがあり遅延を抑えやすい

**向くケース**
- 端末のCPU/GPU性能が低め
- 低電力で常時利用に寄せたい

## C. Web Speech API（Web版の暫定選択肢）
- ブラウザ提供機能を使えるため、アプリ側でSTT基盤を持たなくて済む
- ただし挙動・対応状況はブラウザ依存

**向くケース**
- まずWeb PoCを最短で出したい

---

## 3. 「無料運用」時の現実的な制約

- クラウドAPI課金はないが、以下のコストは残る:
  - 端末電池消費
  - 端末発熱
  - モデル配布容量（アプリサイズ）
- 高精度モデルほど遅延と消費電力が増える

**実装方針**
- 初期モデル: small〜medium級で開始
- 端末ベンチ結果で model tier を自動切替
- 「省電力モード（更新間引き）」をUIで選択可能にする

---

## 4. 日本仕様で先に決めるべきこと

## 4.1 日本語UX
- 句読点の扱い（読みやすさ優先で自動補完）
- 敬語・相づち・言い淀みの表示ポリシー
- 固有名詞（人名・地名）辞書の後段補正
- 文字サイズ固定ではなく、**最小18px以上**を基本値に

## 4.2 アクセシビリティ（国内標準への寄せ）
- JIS X 8341-3:2016 相当を意識したUI設計
  - コントラスト
  - 拡大時の可読性
  - 音声以外チャネル（字幕・バイブ）

## 4.3 法務・プライバシー（日本）
- 個人情報保護法（APPI）を前提に、音声データを個人情報として扱う設計
- 特に**音声特徴から本人認証可能なデータ**は個人識別符号として扱われ得る
- 可能な限りローカル処理に寄せ、クラウド送信時は明示同意
- 利用規約とプライバシーポリシーに以下を明記:
  - 収集するデータ
  - 保存期間
  - 第三者提供の有無
  - 問い合わせ窓口

---

## 5. 技術アーキテクチャ（無料運用版）

```text
Mic
 ↓
VAD / NS / AGC（WebRTC Audio Processing）
 ↓
STT engine（whisper.cpp または Vosk）
 ↓
部分字幕（0.3〜1.0秒）→ 確定字幕（1〜2秒）
 ↓
再提示
  - 字幕再確認
  - 整音原音を再生
```

### 最低限のレイテンシ目標
- 部分結果: 300〜1000ms
- 確定結果: 1〜2秒
- 再生開始: 1秒以内

---

## 6. 開発ステップ（日本語優先）

### Phase 0（1〜2週間）
- whisper.cpp / Vosk の日本語音声でベンチ
- 測定: 遅延、端末温度、電池消費

### Phase 1（2〜4週間）
- 字幕UI（部分・確定の2段表示）
- 「直前10秒を聞き直す」ボタン
- 誤変換フィードバック収集

### Phase 2（運用）
- 辞書チューニング（駅名・人名・業界用語）
- 省電力モード
- オフライン完全対応を既定値化

---

## 7. 具体的なツール選定（今回の要望に対する提案）

- **本命**: whisper.cpp
- **軽量端末向け予備**: Vosk
- **クラウドSTTは初期採用しない**（維持費ゼロを優先）

必要になったら後から、クラウドを「精度強化オプション」として追加する（デフォルトOFF）。

---

## 8. 参照した公式/一次情報
- whisper.cpp (GitHub): https://github.com/ggml-org/whisper.cpp
- whisper.cpp License (MIT): https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE
- OpenAI Whisper (GitHub): https://github.com/openai/whisper
- Vosk API (GitHub): https://github.com/alphacep/vosk-api
- Vosk License (Apache-2.0): https://github.com/alphacep/vosk-api/blob/master/COPYING
- Apple Speech framework: https://developer.apple.com/documentation/speech/sfspeechrecognizer
- Android SpeechRecognizer: https://developer.android.com/reference/android/speech/SpeechRecognizer
- MDN Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- 個人情報保護委員会 APPI Q&A: https://www.ppc.go.jp/personalinfo/faq/APPI_QA/
- デジタル庁 ウェブアクセシビリティ導入ガイドブック: https://www.digital.go.jp/resources/introduction-to-web-accessibility-guidebook/

