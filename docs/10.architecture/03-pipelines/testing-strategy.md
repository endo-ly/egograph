# Pipelines テスト戦略

Pipelines Service のテスト実装に関する標準ガイドライン。

## 1. テストレベルとディレクトリ構成

```
egograph/pipelines/tests/
├── unit/                                  # ユニットテスト（高速、モック使用）
│   ├── test_scheduler.py                 # Scheduler テスト
│   ├── test_dispatcher.py                # Dispatcher テスト
│   ├── test_api.py                       # 管理API テスト
│   ├── test_lock_manager.py              # LockManager テスト
│   ├── test_repository.py                # Repository テスト
│   ├── test_compaction.py                # Compaction 共通機能
│   ├── test_bootstrap_compact.py         # Bootstrap compaction
│   │
│   ├── spotify/                          # Spotify ユニットテスト
│   │   ├── test_collector.py
│   │   ├── test_transform.py
│   │   ├── test_storage.py
│   │   └── test_writer.py
│   │
│   ├── github/                           # GitHub ユニットテスト
│   │   ├── test_collector.py
│   │   ├── test_transform.py
│   │   ├── test_storage.py
│   │   └── test_pipeline.py
│   │
│   ├── browser_history/                  # Browser History ユニットテスト
│   │   ├── test_transform.py
│   │   ├── test_storage.py
│   │   ├── test_compaction.py
│   │   ├── test_schema.py
│   │   └── test_pipeline.py
│   │
│   └── google_activity/                  # Google Activity ユニットテスト
│       ├── test_collector.py
│       ├── test_transform.py
│       ├── test_storage.py
│       ├── test_pipeline.py
│       ├── test_schema.py
│       ├── test_config.py
│       └── test_youtube_api.py
│
├── integration/                           # インテグレーションテスト（モックレスポンス）
│   ├── spotify/
│   │   └── test_pipeline.py              # Collector → Storage 結合
│   ├── github/
│   │   └── test_pipeline.py              # パイプライン全体
│   ├── browser_history/
│   │   └── test_pipeline.py              # Ingest + Compact 結合
│   └── google_activity/
│       └── test_pipeline.py              # パイプライン全体
│
├── e2e/                                  # E2Eテスト（サービス全体）
│   └── test_browser_history_ingest.py    # API → Dispatcher → Executor → Storage
│
├── live/                                 # 実APIテスト（CI除外）
│   ├── spotify/
│   │   └── test_collector.py             # 実Spotify API
│   └── conftest.py                       # .env 読み込み
│
├── fixtures/                             # 共有フィクスチャ
│   ├── conftest.py
│   ├── spotify_responses.py
│   └── github_responses.py
│
└── support/                              # テストサポート
    └── dummy_steps.py
```

---

## 2. テストレベルの目的と依存ポリシー

| レベル | 目的 | 対象 | 外部依存 | CI |
|---|---|---|---|---|
| **Unit** | ロジックの正しさ/境界条件 | 単一コンポーネント | モック | ✅ 常時 |
| **Integration** | 契約・連携の妥当性 | パイプライン全体 | モックレスポンス | ✅ 常時 |
| **E2E** | サービス全体の動作確認 | API→Dispatcher→Executor | in-memory DB | ✅ 常時 |
| **Live** | 実API動作確認 | 実外部サービス | **実API** | ❌ 手動のみ |

---

## 3. pytest マーカー

`live` のみ定義する。Unit/Integration/E2E の区別はディレクトリ構造で表現する。
CI では実行したいディレクトリを明示的に指定し、否定マーカー（`-m "not live"`）は使用しない。

---

## 4. テスト実行コマンド

```bash
# CI用（unit + integration + e2e を明示的に指定）
uv run pytest egograph/pipelines/tests/unit \
              egograph/pipelines/tests/integration \
              egograph/pipelines/tests/e2e --cov=pipelines

# Unit のみ（高速）
uv run pytest egograph/pipelines/tests/unit -v

# 特定ソース
uv run pytest egograph/pipelines/tests/unit/spotify -v

# Live テスト（手動）
uv run pytest egograph/pipelines/tests/live -v -m live
```

---

## 5. AAA パターン

すべてのテストメソッドは以下の3セクションに分割する：

```python
def test_example():
    """テストの目的を日本語で記述。"""
    # Arrange: テストデータの準備とモックの設定
    # Act: テスト対象メソッドの実行
    # Assert: 結果の検証
```

---

## 6. 命名規則

| 項目 | 規則 | 例 |
|---|---|---|
| ファイル名 | `test_{対象}.py` | `test_collector.py` |
| テストメソッド | `test_{メソッド名}_{条件}` | `test_get_recently_played_incremental` |
| Docstring | 日本語で目的を記述 | `"""増分取得でカーソルを使用する。"""` |

---

## 7. CI/CD 統合

GitHub Actions で以下を実行：

```yaml
- name: Run tests
  run: |
    uv run pytest egograph/pipelines/tests/unit \
                  egograph/pipelines/tests/integration \
                  egograph/pipelines/tests/e2e \
                  -v --cov=pipelines --cov-report=xml
```

---

## 8. チェックリスト

PR 作成前に確認：

- [ ] 全テストがパスするか (`uv run pytest egograph/pipelines/tests/unit egograph/pipelines/tests/integration egograph/pipelines/tests/e2e`)
- [ ] AAA パターンで記述されているか
- [ ] テストの目的が日本語 docstring で説明されているか
- [ ] モックが適切に使われているか
- [ ] Live テストには `@pytest.mark.live` が付いているか

---

## 9. テストケース一覧

### 9.1 Core Unit Tests

| ファイル | 対象 | 内容 |
|---|---|---|
| `test_scheduler.py` | ScheduleTriggerApp | CRON/INTERVAL トリガー、misfire |
| `test_dispatcher.py` | RunDispatcher | dispatch_once, heartbeat, lock |
| `test_lock_manager.py` | LockManager | acquire/release/heartbeat |
| `test_repository.py` | WorkflowStateRepository | CRUD 操作 |
| `test_api.py` | FastAPI endpoints | ヘルスチェック、workflow 一覧、手動実行 |

### 9.2 Source Unit Tests

| ディレクトリ | 対象 | 主なテスト |
|---|---|---|
| `unit/spotify/` | Spotify パイプライン | collector, transform, storage, writer |
| `unit/github/` | GitHub パイプライン | collector, transform, storage, pipeline |
| `unit/browser_history/` | Browser History | transform, storage, compaction, schema |
| `unit/google_activity/` | Google Activity | collector, storage, pipeline, schema, transform |

### 9.3 Integration Tests

| ファイル | 対象 | 内容 |
|---|---|---|
| `integration/spotify/test_pipeline.py` | Spotify パイプライン | Collector → Storage 結合 |
| `integration/browser_history/test_pipeline.py` | Browser History | Ingest + Compact 結合 |
| `integration/google_activity/test_pipeline.py` | Google Activity | パイプライン全体 |

### 9.4 E2E Tests

| ファイル | 対象 | 内容 |
|---|---|---|
| `e2e/test_browser_history_ingest.py` | サービス全体 | API → Dispatcher → Executor → Storage |

### 9.5 Live Tests

| ファイル | 対象 | 内容 |
|---|---|---|
| `live/spotify/test_collector.py` | 実 Spotify API | 実際の API 呼び出し（要認証） |
