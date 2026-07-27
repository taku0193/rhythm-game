import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import scipy.io.wavfile
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn
import os
import uuid
import librosa

# --- 初期設定 ---
app = FastAPI()
AUDIO_DIRECTORY = os.path.abspath("static/audio")
os.makedirs(AUDIO_DIRECTORY, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_audio_path(filename: str) -> str:
    if os.path.basename(filename) != filename or not filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Invalid audio filename")
    return os.path.join(AUDIO_DIRECTORY, filename)

# --- モデルのロード ---
print("モデルをロードしています... これには数分かかることがあります。")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用するデバイス: {device}")

model_name = "facebook/musicgen-large"
model_revision = "15ccdc92099879e47b6da12c350cdb71d4eab3ca"
processor = AutoProcessor.from_pretrained(
    model_name,
    revision=model_revision,
)
model = MusicgenForConditionalGeneration.from_pretrained(
    model_name,
    revision=model_revision,
    attn_implementation="eager"
).to(device)

print("モデルのロードが完了しました。")


@app.get("/healthz")
async def healthz():
    return {"service": "musicgen", "status": "ok"}


# --- APIリクエストのデータ形式 ---
class MusicPrompt(BaseModel):
    prompt: str
    duration: int = Field(default=15, ge=1, le=30)

# --- BGM生成APIのエンドポイント ---
@app.post("/generate-bgm")
async def generate_bgm(music_prompt: MusicPrompt):
    try:
        safe_duration = music_prompt.duration
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
        output_path = get_audio_path(output_filename)
        
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

        # ブラウザ側でViteの /api プロキシを通せるよう相対パスを返す
        file_url = f"/audio/{output_filename}"
        
        print(f"生成されたURL: {file_url}")
        
        return {"success": True, "url": file_url, "bpm": bpm}

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return {"success": False, "error": str(e)}

# --- 音声ファイル確認用エンドポイント ---
@app.get("/check-audio/{filename}")
async def check_audio(filename: str):
    file_path = get_audio_path(filename)
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        return {"exists": True, "size": file_size, "path": file_path}
    else:
        return {"exists": False, "path": file_path}

# --- 音声ファイル配信用エンドポイント ---
@app.get("/audio/{filename}")
async def get_audio(filename: str, request: Request):
    file_path = get_audio_path(filename)
    if os.path.exists(file_path):
        # 適切なヘッダーを設定
        headers = {
            "Content-Type": "audio/wav",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD",
            "Access-Control-Allow-Headers": "*"
        }
        
        # ファイルサイズを取得
        file_size = os.path.getsize(file_path)
        
        # Range リクエストの処理
        range_header = request.headers.get("range")
        if range_header:
            try:
                # Range: bytes=start-end の形式を解析
                range_str = range_header.replace("bytes=", "")
                start, end = range_str.split("-")
                start = int(start)
                end = int(end) if end else file_size - 1
                
                # ファイルの一部を読み込み
                with open(file_path, "rb") as f:
                    f.seek(start)
                    data = f.read(end - start + 1)
                
                headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                headers["Content-Length"] = str(len(data))
                
                return Response(
                    content=data,
                    headers=headers,
                    status_code=206
                )
            except Exception as e:
                print(f"Range リクエスト処理エラー: {e}")
        
        # 通常のファイル配信
        return FileResponse(
            file_path, 
            media_type="audio/wav",
            headers=headers
        )
    else:
        raise HTTPException(status_code=404, detail="File not found")

# --- 音声ファイルテスト用エンドポイント ---
@app.get("/test-audio/{filename}")
async def test_audio(filename: str):
    file_path = get_audio_path(filename)
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        
        # ファイルの最初の数バイトを読み込んでWAVヘッダーを確認
        with open(file_path, "rb") as f:
            header = f.read(44)  # WAVヘッダーは44バイト
        
        # WAVファイルの基本的な検証
        is_valid_wav = (
            len(header) >= 44 and
            header[0:4] == b'RIFF' and
            header[8:12] == b'WAVE' and
            header[12:16] == b'fmt '
        )
        
        return {
            "exists": True,
            "size": file_size,
            "path": file_path,
            "is_valid_wav": is_valid_wav,
            "header_info": {
                "riff": header[0:4].decode('ascii', errors='ignore'),
                "wave": header[8:12].decode('ascii', errors='ignore'),
                "fmt": header[12:16].decode('ascii', errors='ignore')
            }
        }
    else:
        return {"exists": False, "path": file_path}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
