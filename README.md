# Live Viewers Count Monitor

YouTubeとTwitchの配信の同時接続数をリアルタイムで監視し、CSVファイルに記録するプログラムです。

## セットアップ

### 1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの作成
```bash
cp config.example.json config.json
```

### 3. APIキーの設定
`config.json`ファイルを編集し、以下のAPIキーを設定してください：

#### YouTube Data API v3
1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. YouTube Data API v3を有効化
3. APIキーを作成し、`youtube_api_key`に設定

#### Twitch API
1. [Twitch Developer Console](https://dev.twitch.tv/console)でアプリケーションを作成
2. クライアントIDを取得し、`twitch_client_id`に設定
3. アクセストークンを取得し、`twitch_access_token`に設定

### 4. 監視対象の設定
`input_streams.csv`ファイルを編集し、監視したい配信を追加してください：

```csv
Name,platform,URL
配信者名,0,https://www.youtube.com/watch?v=VIDEO_ID
配信者名,1,https://www.twitch.tv/username
```

- `platform`: 0=YouTube, 1=Twitch

## 実行

```bash
python main.py
```

## 出力

`viewer_count_log.csv`に以下の形式でデータが記録されます：

```csv
time,youtube,twitch,配信者1,配信者2,...
2025-06-27 14:30:00,1500,800,1000,500,...
```

## ログ

- コンソール出力：実行状況
- `viewer_monitor.log`：詳細なログ

## 停止

`Ctrl+C`でプログラムを停止できます。
