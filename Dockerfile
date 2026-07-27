# ベースとなるNode.jsイメージを指定
FROM node:22-alpine

# コンテナ内の作業ディレクトリを作成
WORKDIR /app

# package.jsonとpackage-lock.jsonをコピー
COPY package*.json ./

# lockfileどおりに依存関係をインストール
RUN npm ci

# プロジェクトの全てのファイルをコピー
COPY . .

# Vite開発サーバーのデフォルトポートを公開
EXPOSE 5173

# 開発サーバーを起動
# host、port、strictPortはvite.config.jsで一元管理する
CMD ["npm", "run", "dev"]
