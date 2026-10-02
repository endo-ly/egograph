---
name: "backend-data-api"
description: "EgoGraph Backend（データ提供API）のAPI仕様書。ヘルスチェック、Spotify・Browser History・GitHub・YouTube・Google Health・Daily TimelineのREST APIを、Tailscale経由でAPI Keyなしに叩いて個人データを参照・動作確認する。"
allowed-tools: "Bash, Read"
---

# Backend Data API

EgoGraph Backend の全 REST API エンドポイント仕様。エージェントが API 経由で個人データを取得・動作確認するためのリファレンス。

## 環境設定

```bash
export BACKEND_BASE="https://egograph-prod.<tailnet>.ts.net"   # tailscale serve の公開URL
```

- 認証は Tailscale の app capability で行う。ACL で capability を付与された端末からのリクエストは、API Key なしで通る
- **API Key は使わない・探さない**。401 が返る場合は、この端末に capability が付与されていないか、serve / Backend の設定漏れ。ユーザーに報告する
- 設定手順は `docs/deploy/backend.md` の「Tailscale app capability 認証」

## エンドポイント一覧

全て GET。`/health`, `/v1/health` 以外は認証対象（capability 付与端末ならヘッダー不要）。

| Method | Path | 説明 |
|--------|------|------|
| `GET` | `/health`, `/v1/health` | DuckDB + R2 readiness（認証不要） |
| `GET` | `/v1/data/spotify/stats/top-tracks` | トップトラック |
| `GET` | `/v1/data/spotify/stats/listening` | 再生統計（日/週/月） |
| `GET` | `/v1/data/browser-history/page-views` | ページビュー一覧 |
| `GET` | `/v1/data/browser-history/top-domains` | ドメインランキング |
| `GET` | `/v1/data/github/pull-requests` | PR イベント |
| `GET` | `/v1/data/github/commits` | コミットイベント |
| `GET` | `/v1/data/github/repositories` | リポジトリ一覧 |
| `GET` | `/v1/data/github/activity-stats` | アクティビティ統計（日/週/月） |
| `GET` | `/v1/data/github/repo-summary-stats` | リポジトリ別サマリー |
| `GET` | `/v1/data/youtube/watch-events` | 視聴イベント一覧 |
| `GET` | `/v1/data/youtube/stats/watching` | 視聴統計（日/週/月） |
| `GET` | `/v1/data/youtube/stats/top-videos` | トップ動画 |
| `GET` | `/v1/data/youtube/stats/top-channels` | トップチャンネル |
| `GET` | `/v1/data/google-health/daily-summary` | 日次健康サマリ |
| `GET` | `/v1/data/google-health/daily-metrics` | 日次Projection（columnar） |
| `GET` | `/v1/data/google-health/timeseries` | sample/interval 時系列 |
| `GET` | `/v1/data/google-health/sessions` | sleep/exercise セッション（columnar） |
| `GET` | `/v1/data/google-health/records/{record_id}` | 完全保存 record の詳細 |
| `GET` | `/v1/data/timeline/daily` | 日次統合タイムライン |

### 共通パラメータ

| パラメータ | 形式 | 説明 |
|-----------|------|------|
| `start_date` / `end_date` | `YYYY-MM-DD` | 期間（両端を含む）。Backend の `TIMEZONE` のローカル日付として解釈 |
| `limit` | int `1〜100` | 取得件数（エンドポイントごとに既定値が異なる） |
| `granularity` | `day` / `week` / `month` | 集計粒度（既定 `day`） |

---

## エンドポイント詳細

### GET /health, /v1/health

DuckDB 接続と R2 の Spotify dataset 読み取りで readiness を確認。認証不要。

```bash
curl -s "${BACKEND_BASE}/v1/health"
```

**Response 200:**
```json
{"status": "ok", "duckdb": "connected", "r2": "accessible", "data_available": true}
```

- 初回投入前（Parquet 未存在）は `data_available: false` で 200

**Response 503:**
```json
{"status": "error", "error": "invalid_readiness: <sanitized reason>"}
```

---

### Spotify

#### GET /v1/data/spotify/stats/top-tracks

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `limit` | | `10` |

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/spotify/stats/top-tracks?start_date=2026-09-01&end_date=2026-09-27&limit=5"
```

**Response 200:**
```json
[
  {
    "track_name": "だから僕は音楽を辞めた",
    "artist": "ヨルシカ",
    "play_count": 12,
    "total_minutes": 51.3,
    "played_at": ["2026-09-26T09:12:03", "2026-09-25T22:01:44"]
  }
]
```

#### GET /v1/data/spotify/stats/listening

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `granularity` | | `day` |

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/spotify/stats/listening?start_date=2026-09-01&end_date=2026-09-27&granularity=week"
```

**Response 200:**
```json
[{"period": "2026-09-21", "total_ms": 12345678, "track_count": 180, "unique_tracks": 95}]
```

---

### Browser History

#### GET /v1/data/browser-history/page-views

| パラメータ | 必須 | 既定 | 説明 |
|-----------|------|------|------|
| `start_date`, `end_date` | ✓ | - | |
| `limit` | | `50` | |
| `browser` | | - | ブラウザで絞り込み |
| `profile` | | - | プロファイルで絞り込み |
| `include_reload` | | `null` | `true` で `transition='reload'` を含める（既定は除外） |

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/browser-history/page-views?start_date=2026-09-27&end_date=2026-09-27&limit=20"
```

**Response 200:**
```json
[
  {
    "page_view_id": "…",
    "started_at": "2026-09-27T01:02:03",
    "ended_at": "2026-09-27T01:05:10",
    "url": "https://example.com/",
    "title": "Example",
    "browser": "edge",
    "profile": "Default",
    "transition": "link",
    "visit_span_count": 1
  }
]
```

#### GET /v1/data/browser-history/top-domains

パラメータは page-views と同じ（`limit` 既定 `20`）。

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/browser-history/top-domains?start_date=2026-09-01&end_date=2026-09-27"
```

**Response 200:**
```json
[{"domain": "github.com", "page_view_count": 320, "unique_urls": 140}]
```

---

### GitHub

#### GET /v1/data/github/pull-requests

| パラメータ | 必須 | 既定 | 説明 |
|-----------|------|------|------|
| `start_date`, `end_date` | ✓ | - | |
| `owner`, `repo` | | - | 絞り込み |
| `state` | | - | `open` / `closed` |
| `limit` | | `100` | |

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/github/pull-requests?start_date=2026-09-01&end_date=2026-09-27&repo=egograph"
```

**Response 200（主要フィールド）:**
```json
[
  {
    "pr_event_id": "…",
    "pr_key": "endo-ly/egograph#192",
    "owner": "endo-ly",
    "repo": "egograph",
    "repo_full_name": "endo-ly/egograph",
    "pr_number": 192,
    "action": "merged",
    "state": "closed",
    "is_merged": true,
    "title": "fix(pipelines): harden Google Health ingest storage",
    "updated_at": "2026-09-26T12:00:00",
    "additions": 120,
    "deletions": 40
  }
]
```

その他: `pr_id`, `labels`, `base_ref`, `head_ref`, `created_at`, `closed_at`, `merged_at`, `comments_count`, `review_comments_count`, `reviews_count`, `commits_count`, `changed_files_count`

#### GET /v1/data/github/commits

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `owner`, `repo` | | - |
| `limit` | | `100` |

**Response 200:**
```json
[
  {
    "commit_event_id": "…",
    "owner": "endo-ly",
    "repo": "egograph",
    "repo_full_name": "endo-ly/egograph",
    "sha": "8316799…",
    "message": "fix(pipelines): …",
    "committed_at": "2026-09-26T11:50:00",
    "changed_files_count": 5,
    "additions": 120,
    "deletions": 40
  }
]
```

#### GET /v1/data/github/repositories

期間指定なし（master データ）。

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `owner` | | - |
| `limit` | | `100` |

**Response 200（主要フィールド）:** `repo_id`, `repo_full_name`, `description`, `is_private`, `is_fork`, `archived`, `primary_language`, `topics`, `stargazers_count`, `created_at`, `updated_at`, `pushed_at`, `repo_summary_text`

#### GET /v1/data/github/activity-stats

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `granularity` | | `day` |

**Response 200:**
```json
[{"period": "2026-09-26", "prs_created": 2, "prs_merged": 1, "commits_count": 8, "additions": 300, "deletions": 90}]
```

#### GET /v1/data/github/repo-summary-stats

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `owner`, `repo` | | - |

**Response 200:**
```json
[
  {
    "owner": "endo-ly",
    "repo": "egograph",
    "repo_full_name": "endo-ly/egograph",
    "prs_total": 10,
    "prs_merged": 8,
    "commits_total": 42,
    "total_additions": 3000,
    "total_deletions": 1200,
    "last_pr_updated_at": "2026-09-26T12:00:00",
    "last_commit_at": "2026-09-26T11:50:00"
  }
]
```

---

### YouTube

#### GET /v1/data/youtube/watch-events

| パラメータ | 必須 | 既定 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | - |
| `limit` | | 省略時は全件 |

**Response 200:**
```json
[
  {
    "watch_event_id": "…",
    "watched_at": "2026-09-26T13:00:00",
    "video_id": "abc123",
    "video_url": "https://www.youtube.com/watch?v=abc123",
    "video_title": "…",
    "channel_id": "UC…",
    "channel_name": "…",
    "content_type": "video"
  }
]
```

#### GET /v1/data/youtube/stats/watching

`start_date`, `end_date`（必須）, `granularity`（既定 `day`）

**Response 200:**
```json
[{"period": "2026-09-26", "watch_event_count": 15, "unique_video_count": 12, "unique_channel_count": 8}]
```

#### GET /v1/data/youtube/stats/top-videos

`start_date`, `end_date`（必須）, `limit`（既定 `10`）

**Response 200:**
```json
[{"video_id": "abc123", "video_title": "…", "channel_id": "UC…", "channel_name": "…", "watch_event_count": 4}]
```

#### GET /v1/data/youtube/stats/top-channels

`start_date`, `end_date`（必須）, `limit`（既定 `10`）

**Response 200:**
```json
[{"channel_id": "UC…", "channel_name": "…", "watch_event_count": 20, "unique_video_count": 11}]
```

---

### Google Health

#### GET /v1/data/google-health/daily-summary

`start_date`, `end_date`（必須）

```bash
curl -s \
  "${BACKEND_BASE}/v1/data/google-health/daily-summary?start_date=2026-09-20&end_date=2026-09-27"
```

**Response 200:**
```json
[
  {
    "date": "2026-09-26",
    "steps": 8421,
    "distance": 6100000,
    "total_calories": 2300,
    "active_energy_burned": 450,
    "active_minutes": 62,
    "active_zone_minutes": 30,
    "resting_heart_rate": 58,
    "daily_hrv": 45.2,
    "daily_oxygen_saturation": 97.1,
    "daily_respiratory_rate": 14.2,
    "sleep_duration": 420,
    "daily_vo2_max": 44.0
  }
]
```

値が無い指標は `null`。

#### GET /v1/data/google-health/daily-metrics

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | |
| `data_type` | | Google Health data type（後述）。省略時は全 type |

**Response 200（columnar）:**
```json
{"columns": ["date", "metric", "value", "unit"], "rows": [["2026-09-26", "steps", 8421, "count"]]}
```

#### GET /v1/data/google-health/timeseries

| パラメータ | 必須 | 既定 | 説明 |
|-----------|------|------|------|
| `data_type` | ✓ | - | sample / interval 系の data type |
| `start_at`, `end_at` | ✓ | - | ISO-8601 **timezone offset 必須**（例 `2026-09-26T00:00:00+09:00`） |
| `metric` | | - | 複数 metric を持つ data type では必須 |
| `resolution` | | `auto` | `auto` / `raw` / `5m` / `15m` / `30m` / `1h` |

- `auto` は最大 80 bucket 程度になる解像度を自動選択
- `raw` は 1000 行を超えると 400（集約解像度を指定し直す）
- `+` は URL エンコード（`%2B`）が必要。`--data-urlencode` を使うと安全

```bash
curl -s -G "${BACKEND_BASE}/v1/data/google-health/timeseries" \
  --data-urlencode "data_type=heart-rate" \
  --data-urlencode "start_at=2026-09-26T00:00:00+09:00" \
  --data-urlencode "end_at=2026-09-27T00:00:00+09:00" \
  --data-urlencode "resolution=1h"
```

**Response 200:**
```json
{
  "type": "heart-rate",
  "metric": "<metric_name>",
  "unit": "<unit>",
  "resolution": "1h",
  "stats": {"sum": null, "avg": 68.2, "min": 52, "max": 131},
  "series": {"columns": ["…"], "rows": [["…"]]},
  "highlights": {"peaks": [], "rises": [], "falls": []}
}
```

#### GET /v1/data/google-health/sessions

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `start_date`, `end_date` | ✓ | |
| `data_type` | | `sleep` / `exercise`。省略時は両方 |

**Response 200（columnar）:**
```json
{
  "columns": ["id", "type", "start", "end", "duration_s", "session_type"],
  "rows": [["<record_id>", "sleep", "2026-09-25T23:40:00+09:00", "2026-09-26T06:50:00+09:00", 25800, "…"]]
}
```

`start` / `end` は Backend の `TIMEZONE` のローカル時刻。`id` を records エンドポイントに渡すと payload 全体を取得できる。

#### GET /v1/data/google-health/records/{record_id}

```bash
curl -s "${BACKEND_BASE}/v1/data/google-health/records/<record_id>"
```

**Response 200:**
```json
{"id": "…", "type": "sleep", "kind": "session", "date": "2026-09-26", "payload": {"…": "…"}}
```

**Response 404:** record が存在しない

#### Google Health data type 一覧

| kind | data type |
|------|-----------|
| DAILY | `total-calories`, `daily-vo2-max`, `daily-resting-heart-rate`, `daily-heart-rate-variability`, `daily-heart-rate-zones`, `daily-oxygen-saturation`, `daily-respiratory-rate`, `daily-sleep-temperature-derivations` |
| INTERVAL | `steps`, `distance`, `active-energy-burned`, `active-minutes`, `active-zone-minutes`, `activity-level`, `sedentary-period`, `calories-in-heart-rate-zone`, `time-in-heart-rate-zone`, `floors`, `altitude`, `swim-lengths-data` |
| SAMPLE | `heart-rate`, `heart-rate-variability`, `oxygen-saturation`, `respiratory-rate`, `respiratory-rate-sleep-summary`, `skin-temperature`, `vo2-max`, `run-vo2-max` |
| SESSION | `sleep`, `exercise` |

正本は `egograph/pipelines/sources/google_health/data_types.py` の `DATA_TYPES`。timeseries は SAMPLE / INTERVAL、sessions は SESSION を指定する。

---

### GET /v1/data/timeline/daily

複数データソースを1日分、時刻順に統合したタイムライン。仕様の詳細は `docs/architecture/daily-timeline.md`。

| パラメータ | 必須 | 既定 | 説明 |
|-----------|------|------|------|
| `date` | ✓ | - | `timezone` 上のローカル日付 |
| `timezone` | | Backend の `TIMEZONE`（未設定時 `Asia/Tokyo`） | IANA timezone |
| `sources` | | 全 source | 複数指定可（`sources=spotify&sources=github`）。`spotify` / `youtube` / `browser_history` / `github` / `google_health` |
| `gap_minutes` | | `120` | この分数以上の観測欠落を `gaps` に返す（`0` で無効、最大 `1440`） |
| `include_correlations` | | `true` | 関連候補を返す |
| `include_raw_refs` | | `false` | 元 dataset と record id を返す |
| `limit` | | `500` | `items` の最大件数（最大 `2000`） |

```bash
curl -s -G "${BACKEND_BASE}/v1/data/timeline/daily" \
  --data-urlencode "date=2026-09-26" \
  --data-urlencode "timezone=Asia/Tokyo"
```

**Response 200（トップレベル）:**
```json
{
  "date": "2026-09-26",
  "timezone": "Asia/Tokyo",
  "range": {"start_local": "…", "end_local": "…", "start_utc": "…", "end_utc": "…"},
  "items": [{"event_id": "…", "source": "spotify", "kind": "music_play", "started_at_utc": "…", "started_at_local": "…", "title": "…"}],
  "correlations": [],
  "gaps": [],
  "daily_summaries": {"google_health": {"…": "…"}},
  "coverage": {"spotify": {"…": "…"}},
  "meta": {"item_count": 120, "truncated": false, "generated_at": "…"}
}
```

`google_health` は `items` に入らず `daily_summaries` / `coverage` に反映される。

---

## 確認レシピ

### 1. 死活確認

```bash
curl -sf "${BACKEND_BASE}/v1/health" | jq . || echo "DOWN"
```

### 2. データソース別の直近データ有無（今日から7日間）

```bash
END=$(date +%F); START=$(date -d '7 days ago' +%F)
for path in \
  "spotify/stats/listening" \
  "browser-history/top-domains" \
  "github/activity-stats" \
  "youtube/stats/watching" \
  "google-health/daily-summary"; do
  count=$(curl -s \
    "${BACKEND_BASE}/v1/data/${path}?start_date=${START}&end_date=${END}" | jq 'length')
  echo "${path}: ${count} rows"
done
```

0 件のソースは Pipelines 側の取り込み・compact を疑い、`pipelines-monitoring` スキルで該当 workflow の run を確認する。

### 3. 特定日の行動を俯瞰する

```bash
curl -s -G "${BACKEND_BASE}/v1/data/timeline/daily" \
  --data-urlencode "date=$(date -d yesterday +%F)" \
  | jq '{items: .meta.item_count, truncated: .meta.truncated, gaps: (.gaps | length), coverage}'
```

### 4. 睡眠セッションの詳細を辿る

```bash
# 1. セッション一覧から record id（先頭列 id）を取り出す
curl -s \
  "${BACKEND_BASE}/v1/data/google-health/sessions?start_date=2026-09-26&end_date=2026-09-26&data_type=sleep" \
  | jq -r '.rows[][0]'
# 2. record 詳細
curl -s "${BACKEND_BASE}/v1/data/google-health/records/<record_id>" | jq .payload
```

---

## エラーレスポンス

| ステータス | 意味 | 例 |
|-----------|------|-----|
| `400` | バリデーションエラー | `{"detail": "invalid_date_range: start_date must be on or before end_date"}` |
| `401` | 端末に capability が付与されていない（serve / Backend の設定漏れを含む） | `{"detail": "Invalid API key"}` |
| `404` | リソース未存在（Google Health record） | |
| `422` | FastAPI の型/範囲チェック違反（`limit=0`、`granularity=year` 等） | |
| `503` | health の readiness failure | `{"status": "error", "error": "invalid_readiness: …"}` |

エラーメッセージは `invalid_<field>: <reason>` 形式。Parquet 未存在の期間は多くのエンドポイントで空配列 `[]` を返す。

---

## ガードレール

- 読み取り専用 API。データを変更するエンドポイントは存在しない
- API Key を探したり、ファイル・環境変数から読み取ったりしない
- 広い期間 × 全件取得は R2 読み込みが重くなるため、まず集計系（stats / summary）で当たりを付けてから明細を取る
- 取得した個人データ（閲覧 URL、健康データ等）は必要最小限だけ会話に出す
