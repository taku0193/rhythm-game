# Rhythm Game (MediaPipe x MusicGen)

**カメラの前で身体を動かすだけで遊べる、姿勢推定ベースのリズムゲーム。**  
MediaPipeのPose Landmarkerで動きを検出し、生成BGMのBPMに合わせて的を出現させる“踊れる”ミニゲームです。

---

## 何ができる？
- **ハンズフリーでプレイ**：カメラ入力のみで操作  
- **リアルタイム姿勢推定**：MediaPipe Pose Landmarker  
- **BGM生成＋BPM同期**：MusicGenで曲を作り、ビートに合わせてゲーム進行  
- **スコア/コンボ/リザルト**：ハイスコア保存・統計表示

---

## デモの流れ
1. ブラウザでカメラ許可  
2. BGMを生成（任意）  
3. 的に身体を合わせてヒット  
4. リザルトでスコア確認

---

## 技術スタック
- **Frontend**: Vue 3 + Vite  
- **Vision**: `@mediapipe/tasks-vision`  
- **Backend**: FastAPI + MusicGen + librosa  

---

## セットアップ（フロント）
```sh
npm install
npm run dev
```

---

## セットアップ（バックエンド）
```sh
cd backend
pip install -r requirements.txt
python main.py
```

---

## Docker起動（GPU推奨）
```sh
docker compose up --build
```

---

## 動作環境/注意点
- ブラウザで**カメラのアクセス許可**が必要  
- BGM生成は**GPUがあると高速**（CPUでも動作可能だが時間がかかる）  
- 想定URL:  
  - フロント: `http://localhost:5173`  
  - API: `http://localhost:8000`  

---

## 主要ファイル
- `src/App.vue`：ゲームロジックと描画の中核  
- `backend/main.py`：BGM生成APIと音声配信  

---

## 開発メモ（必要に応じて追記）
- スコア/統計は `localStorage` に保存  
- BPMは生成したWAVを解析して算出  

