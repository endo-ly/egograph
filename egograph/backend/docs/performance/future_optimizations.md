# 将来的な最適化案

このドキュメントでは、現時点では実装を見送った最適化手法を記録する。
将来的にパフォーマンス要件が変化した際の参考として活用する。

## B3: DuckDBコネクション再利用

### 概要
共有コネクションプールによるDuckDB初期化コストの削減。
現在はリクエストごとに新規コネクションを作成しているが、これをプール化して再利用する。

### 期待効果
- **削減時間**: -0.5秒/リクエスト
- **適用範囲**: R2からの大容量Parquetスキャンクエリ全般

### 見送り理由
1. **スレッドセーフ性の問題**: DuckDBは基本的にシングルスレッド想定の設計
2. **チャット履歴DBとの衝突リスク**:
   - チャット履歴DB（`:memory:`）と統計クエリ（R2スキャン）を同一コネクションで扱うと状態が混在
   - トランザクション分離が複雑になる
3. **実装複雑性 >> 効果**:
   - ロック管理、エラーハンドリング、リソースリークの防止など複雑な実装が必要
   - 得られる効果（0.5秒）に対して複雑性が高すぎる

### 採用条件
以下の条件をすべて満たす場合のみ検討する：

- シングルプロセス運用（Uvicorn workers=1）
- READ ONLYクエリのみ（チャット履歴DBとの分離が不要）
- クエリ頻度が非常に高い（秒間10リクエスト以上）

### 実装のポイント
- `threading.Lock`によるコネクション排他制御
- コネクション状態の定期的なヘルスチェック
- タイムアウト時の強制切断と再接続

### 参考資料
- [DuckDB Python API - Concurrency](https://duckdb.org/docs/api/python/overview.html#concurrency)
- 過去の性能測定結果: `backend/tests/performance/test_query_performance.py`

---

## B4: クエリ結果キャッシング

### 概要
TTL付きLRUキャッシュによる同一クエリの高速化。
同じパラメータでのクエリが繰り返される場合、キャッシュからレスポンスを返す。

### 期待効果
- **削減時間**: -90%（2回目以降のクエリ）
- **適用範囲**: 繰り返しクエリが発生するケース

### 有効なケース
- ダッシュボードでの定期的な統計表示
- 同じ期間の集計を複数ユーザーが閲覧
- モニタリング・監視ツールからの定期ポーリング

### 採用条件
以下のいずれかを満たす場合に検討：

- 運用ログで同一クエリの繰り返しが**30%以上**確認された場合
- リアルタイム性よりもレスポンス速度を優先すべき機能（例：月次レポート）
- B1+B2実装後もユーザー体感が遅い（3秒以上）

### 実装のポイント

#### キャッシュキー設計
```python
cache_key = f"{tool_name}:{hash(json.dumps(params, sort_keys=True))}"
```

#### TTL設定
- **推奨値**: 6時間
  - 理由: Ingestは1日2回実行（2時, 14時）
  - 最新データ反映までの許容遅延とのバランス
- **最大サイズ**: 100エントリ（約10MB）

#### キャッシュ無効化
- Ingest完了時にWebhookで全キャッシュクリア
- 将来的には特定期間のキャッシュのみクリア（例：今月分のみ）

### デメリット
- メモリ消費量の増加
- データ更新のリアルタイム性が損なわれる
- キャッシュキー設計のミスによるバグリスク

### 実装の段階
1. **MVP**: シンプルなメモリ内LRUキャッシュ（`functools.lru_cache`）
2. **拡張**: Redis等の外部キャッシュ（複数ワーカー対応）
3. **高度化**: キャッシュヒット率の監視、自動TTL調整

### 参考資料
- [cachetools](https://github.com/tkem/cachetools): Python用の拡張可能なキャッシュライブラリ
- [aiocache](https://github.com/aio-libs/aiocache): 非同期対応キャッシュフレームワーク

---

## C2: 事前集計ビューの作成

### 概要
Ingest時に月次トップ100曲を事前計算してParquet保存。
クエリ時はGROUP BYなしで事前集計済みデータを読み取るだけ。

### 期待効果
- **削減時間**: -80%（18秒 → 2秒）
- **予測可能性**: クエリ時間が安定（データ量に依存しない）

### メリット
1. **劇的な高速化**: GROUP BYが不要
2. **予測可能な性能**: 常にフルスキャン不要
3. **複雑なクエリへの対応**: ジョイン・サブクエリも高速化

### デメリット
1. **ストレージコスト増**:
   - 月次トップ100 × 12ヶ月 = 約1200レコード/年
   - 1ユーザーあたり10KB程度
2. **Ingest時間増**: +30秒〜1分
3. **リアルタイム性低下**: 事前集計済みデータなので最新データの反映が遅れる
4. **柔軟性の低下**: 事前定義した集計軸以外のクエリには効果なし

### 採用条件
以下の条件を満たす場合のみ検討：

- **B1+B2実装後も5秒以上かかる**
- ユーザー数が増加してストレージコストが許容範囲内（月額$10未満）
- Ingest時間の増加が許容できる（現在5分 → 6分）

### 実装の段階

#### MVP: 月次トップ100のみ
```
s3://ego-graph-data/aggregated/spotify/top_tracks_monthly/
  └── year=2024/
      ├── month=01/top100.parquet
      ├── month=02/top100.parquet
      └── ...
```

**カラム構成**:
```
user_id, year, month, track_id, track_name, artist_name, play_count, total_play_time_ms, rank
```

#### 拡張: 複数月対応
- 3ヶ月、6ヶ月、1年のロールアップ集計
- 過去データの再集計バッチジョブ

#### 高度化: 多軸集計
- アーティスト別トップ100
- ジャンル別統計
- 時間帯別プレイパターン

### Ingest実装のポイント
```python
# ingest/spotify/aggregator.py（新規作成）
def create_monthly_aggregates(plays: list[dict], year: int, month: int):
    df = pl.DataFrame(plays)
    top100 = (
        df.group_by("track_id")
        .agg([
            pl.col("track_name").first(),
            pl.col("artist_name").first(),
            pl.count().alias("play_count"),
            pl.col("duration_ms").sum().alias("total_play_time_ms"),
        ])
        .sort("play_count", descending=True)
        .head(100)
        .with_row_index("rank", offset=1)
    )
    return top100
```

### クエリ実装のポイント
```python
# backend/domain/tools/spotify_stats.py
def _query_precomputed_top_tracks(start_date: date, end_date: date):
    # 事前集計データを単純にスキャン
    query = """
    SELECT * FROM read_parquet('s3://ego-graph-data/aggregated/spotify/top_tracks_monthly/**/*.parquet')
    WHERE year BETWEEN ? AND ?
      AND month BETWEEN ? AND ?
    ORDER BY year, month, rank
    """
    # GROUP BY不要、集計済み
```

### 測定方法
事前集計の効果を測定するには以下を比較：

1. **現在（B1+B2適用後）**: フルスキャン + GROUP BY
2. **事前集計**: 集計済みParquetの読み取りのみ

測定スクリプト: `backend/tests/performance/benchmark_aggregated_view.py`（未作成）

### 参考資料
- [DuckDB - Parquet Partitioning](https://duckdb.org/docs/data/partitioning/overview.html)
- [Polars - Group By Performance](https://pola-rs.github.io/polars-book/user-guide/howcani/operations/group_by.html)
- Redshift Materialized Views設計パターン

---

## 採用判断フローチャート

```
ユーザー体感が遅い（3秒以上）
  ↓
[B1] インデックス活用（必須）
  ↓
まだ遅い？（2秒以上）
  ↓ Yes
[B2] カラムプルーニング（必須）
  ↓
まだ遅い？（2秒以上）
  ↓ Yes
同一クエリが30%以上繰り返される？
  ↓ Yes               ↓ No
[B4] キャッシング      まだ遅い？（5秒以上）
                        ↓ Yes
                      [C2] 事前集計ビュー
                        ↓
                      それでも遅い？（5秒以上）
                        ↓ Yes
                      [B3] コネクションプール
                       （最終手段、慎重に検討）
```

---

## 更新履歴
- 2026-01-17: 初版作成
