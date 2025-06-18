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

# PyTorchの最新版をインストール（CUDA 12.1対応）
RUN pip3 install --upgrade --no-cache-dir torch>=2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 作業ディレクトリを作成
WORKDIR /app

# requirements.txtをコピーしてライブラリをインストール
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# プロジェクトファイルをコピー
COPY . .

# サーバーを起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]