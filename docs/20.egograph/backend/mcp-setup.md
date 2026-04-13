# MCP Server Configuration

EgoGraph Backend は `/mcp` パスで MCP (Model Context Protocol) エンドポイントを提供する。

## エンドポイント

| URL | Transport | 備考 |
|---|---|---|
| `http://<host>:<port>/mcp` | Streamable HTTP | REST API と同じポート |

## 認証

`BACKEND_API_KEY` 環境変数が設定されている場合、`X-API-Key` ヘッダーが必須。

## egopulse 設定例

`~/.egopulse/mcp.json` または `~/.egopulse/workspace/mcp.json` に配置:

### API Key 認証あり

```json
{
  "mcpServers": {
    "egograph": {
      "transport": "streamable_http",
      "endpoint": "http://127.0.0.1:8000/mcp",
      "headers": {
        "x-api-key": "<your-backend-api-key>"
      },
      "request_timeout_secs": 120
    }
  }
}
```

### 認証なし（ローカル開発）

```json
{
  "mcpServers": {
    "egograph": {
      "transport": "streamable_http",
      "endpoint": "http://127.0.0.1:8000/mcp",
      "request_timeout_secs": 120
    }
  }
}
```

## 利用可能なツール

| ツール名 | 内容 |
|---|---|
| `get_top_tracks` | 指定期間のSpotifyトップトラック |
| `get_listening_stats` | Spotify再生統計（日/週/月） |
| `get_page_views` | Browser History ページビュー一覧 |
| `get_top_domains` | Browser History ドメインランキング |
| `get_pull_requests` | GitHub PRイベント |
| `get_commits` | GitHub コミットイベント |
| `get_repositories` | GitHub リポジトリ一覧 |
| `get_activity_stats` | GitHub アクティビティ統計 |
| `get_repo_summary_stats` | GitHub リポジトリ別サマリー |
| `data_query` | DuckDB生SQL（SELECTのみ） |
