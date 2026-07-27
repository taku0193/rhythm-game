# Rhythm Game (MediaPipe x MusicGen)

![Vue](https://img.shields.io/badge/Vue%203-42b883?style=flat-square&logo=vue.js&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-00A67E?style=flat-square&logo=google&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![MusicGen](https://img.shields.io/badge/MusicGen-111111?style=flat-square&logo=meta&logoColor=white)

**カメラの前で身体を動かすだけで遊べる、姿勢推定ベースのリズムゲーム。**  
MediaPipeのPose Landmarkerで動きを検出し、生成BGMのBPMに合わせて的を出現させる“踊れる”ミニゲームです。

---

## 🧩 何ができる？
- **ハンズフリーでプレイ**：カメラ入力のみで操作  
- **リアルタイム姿勢推定**：MediaPipe Pose Landmarker  
- **BGM生成＋BPM同期**：MusicGenで曲を作り、ビートに合わせてゲーム進行  
- **スコア/コンボ/リザルト**：ハイスコア保存・統計表示

---

## ▶️ デモの流れ
1. ブラウザでカメラ許可  
2. BGMを生成（任意）  
3. 的に身体を合わせてヒット  
4. リザルトでスコア確認

---

## 🗺️ 手順の図解
```
起動
  ↓
カメラ許可
  ↓
（任意）BGM生成 → BPM解析 → ビート同期
  ↓
ゲーム開始
  ↓
身体で的をヒット
  ↓
スコア/コンボ更新
  ↓
リザルト表示 → ハイスコア保存
```

---

## 🎯 ゲーム仕様（概要）
- **操作**：カメラの前で体を動かし、的の位置に身体を合わせる  
- **判定**：接近距離と反応時間で評価（Perfect / Good）  
- **スコア**：ヒットで加点、連続ヒットでコンボ倍率  
- **レベル**：難易度1〜3（的の数・半径・出現間隔が変化）  
- **リザルト**：最終スコア、命中数、コンボ、統計表示  
- **保存**：ハイスコアと統計を `localStorage` に保存  

---

## 🧰 技術スタック
- **Frontend**: Vue 3 + Vite  
- **Vision**: `@mediapipe/tasks-vision`  
- **Backend**: FastAPI + MusicGen + librosa  

---

## 🛠️ セットアップ（フロント）
```sh
npm ci
npm run dev
```

---

## 🧪 セットアップ（バックエンド）
```sh
cd backend
python3 -m pip install \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121
python3 -m pip install -r requirements.txt
python3 main.py
```

---

## 🐳 Docker起動（GPU推奨）
```sh
docker volume create rhythm-game_huggingface_cache
docker compose up --build --force-recreate -d
docker compose ps
curl http://127.0.0.1:5173/
curl http://127.0.0.1:5173/api/healthz
```

初回のみMusicGenモデルの取得とロードに数分かかります。モデルはDockerの
`huggingface_cache` volumeへ保存されるため、コンテナ再作成後も再利用されます。

この環境ではDocker bridgeのポート転送を使わず、Linuxのhost networkで
5173（フロント）と8000（API）を公開します。そのため`docker compose ps`の
`PORTS`欄が空でも正常です。

MacからSSH転送する場合は、ViteのAPI proxyを通すため5173だけを転送します。

```sh
ssh -N -L 5173:127.0.0.1:5173 <user>@<lacar-host>
```

---

## ⚠️ 動作環境/注意点
- ブラウザで**カメラのアクセス許可**が必要  
- BGM生成は**GPUがあると高速**（CPUでも動作可能だが時間がかかる）  
- 想定URL:  
  - フロント: `http://localhost:5173`  
  - APIヘルスチェック: `http://localhost:5173/api/healthz`

---

## 🗂️ 主要ファイル
- `src/App.vue`：ゲームロジックと描画の中核  
- `backend/main.py`：BGM生成APIと音声配信  

---

## 📝 開発メモ（必要に応じて追記）
- スコア/統計は `localStorage` に保存  
- BPMは生成したWAVを解析して算出  
