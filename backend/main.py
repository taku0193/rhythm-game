import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import scipy.io.wavfile
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
import uuid
from fastapi.middleware.cors import CORSMiddleware
import librosa

# --- 初期設定 ---
app = FastAPI()
origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- モデルのロード ---
print("モデルをロードしています... これには数分かかることがあります。")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用するデバイス: {device}")

# ▼▼▼ モデル名を 'large' に戻す ▼▼▼
processor = AutoProcessor.from_pretrained("facebook/musicgen-large")
model = MusicgenForConditionalGeneration.from_pretrained(
    "facebook/musicgen-large",
    attn_implementation="eager"
).to(device)

print("モデルのロードが完了しました。")

# --- APIリクエストのデータ形式 ---
class MusicPrompt(BaseModel):
    prompt: str
    duration: int = 15

# --- BGM生成APIのエンドポイント ---
@app.post("/generate-bgm")
async def generate_bgm(music_prompt: MusicPrompt, request: Request):
    try:
        safe_duration = min(music_prompt.duration, 30)
        print(f"BGM生成リクエストを受信: prompt='{music_prompt.prompt}', duration={safe_duration}s (リクエスト: {music_prompt.duration}s)")
        
        inputs = processor(
            text=[music_prompt.prompt],
            padding=True,
            return_tensors="pt",
        ).to(device)

        print("音楽の生成を開始します...")
        max_new_tokens = int(safe_duration * 50) 
        audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)
        print("音楽の生成が完了しました。")

        sampling_rate = model.config.audio_encoder.sampling_rate
        unique_id = uuid.uuid4()
        output_filename = f"generated_{unique_id}.wav"
        output_path = os.path.join("static/audio", output_filename)
        
        scipy.io.wavfile.write(output_path, rate=sampling_rate, data=audio_values[0, 0].cpu().numpy())
        print(f"ファイルを保存しました: {output_path}")

        print("BPMを解析しています...")
        y, sr = librosa.load(output_path, sr=sampling_rate)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        
        # tempoがnumpy配列の場合があるので、適切に処理する
        if hasattr(tempo, '__iter__') and not isinstance(tempo, str):
            tempo_value = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            tempo_value = float(tempo)
        
        bpm = round(tempo_value)
        
        print(f"解析されたBPM: {bpm}")

        file_url = f"{str(request.base_url)}static/audio/{output_filename}"
        
        return {"success": True, "url": file_url, "bpm": bpm}

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)