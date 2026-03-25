# Spotify データソース設計

## 1. 概要

Spotifyの再生履歴を取り込み、**分析（Analytics）** を実現するための設計。

- **Cloudflare R2 + DuckDB**: すべての再生ログをParquet形式で保存し、正確な集計を行う。

> **Note**: 日次要約のベクトル化・Qdrantでの意味検索は将来拡張機能として検討中（未実装）。

---

## 2. データ構造 (Input)

Spotify API から以下を取得：

### 2.1 Recently Played
- `played_at` (ISO8601)
- `track` (id, name, album, artists, duration_ms, popularity, explicit)

### 2.2 Track Master
- `track_id`, `name`
- `artist_ids`, `artist_names`
- `album_id`, `album_name`
- `duration_ms`, `popularity`, `explicit`, `preview_url`

### 2.3 Artist Master
- `artist_id`, `name`
- `genres`
- `popularity`, `followers_total`

---

## 3. クエリ戦略

現状はDuckDBによるSQLクエリで集計・検索を行う。

| ユーザーの質問 | 意図 | 使用ツール | 処理内容 |
|---|---|---|---|
| 「先週**何回**ミセスを聴いた？」 | 定量分析 | **SQL (DuckDB)** | `COUNT(*)` クエリを実行し、正確な回数を返す。 |
| 「最近**どんな感じ**の曲聴いてる？」 | 定性要約 | **SQL + LLM** | 直近の再生履歴を取得し、LLMに傾向分析させる。 |
| 「**悲しい時**によく聴く曲は？」 | パターン発見 | **SQL + LLM** | 時間帯・曜日でフィルタリングし、LLMでパターン分析。 |
| 「去年のクリスマスの**セットリスト**教えて」 | 事実列挙 | **SQL (DuckDB)** | 特定日のログを全件リストアップする。 |

> **将来拡張**: 日次要約のベクトル化・Qdrantによる意味検索を検討中。
> 要約テキストのEmbedding化により、「雰囲気」や「ムード」での検索を実現予定。

---

## 6. 考慮事項

- **Audio Features**: Spotify API で提供終了しているため取得しない。
- **Genres**: アーティストに依存するため空配列が多い。集計時は "unknown" として扱う。
- **Preview URL**: 権利都合で null が多い。UI 側で存在チェックが必須。
