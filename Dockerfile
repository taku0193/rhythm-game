# ベースとなるNode.jsイメージを指定
FROM node:18-alpine

# コンテナ内の作業ディレクトリを作成
WORKDIR /app

# package.jsonとpackage-lock.jsonをコピー
COPY package*.json ./

# 依存関係をインストール
RUN npm install

# プロジェクトの全てのファイルをコピー
COPY . .

# Vite開発サーバーのデフォルトポートを公開
EXPOSE 5173

# 開発サーバーを起動
# --host 0.0.0.0 を指定することで、コンテナ外からアクセス可能にする
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]