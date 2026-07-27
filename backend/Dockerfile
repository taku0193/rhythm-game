# NVIDIAの公式CUDAイメージをベースにする
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# 環境変数の設定
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 必要なツールとPythonをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# CUDA 12.1向けに互換バージョンを揃えてPyTorchをインストール
RUN python3 -m pip install --no-cache-dir \
    torch==2.5.1 \
    torchvision==0.20.1 \
    torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu121

# 作業ディレクトリを作成
WORKDIR /app

# requirements.txtをコピーしてライブラリをインストール
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# プロジェクトファイルをコピー
COPY . .

EXPOSE 8000

# サーバーを起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
