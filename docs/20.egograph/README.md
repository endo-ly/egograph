# EgoGraph

Personal Data Warehouse。各種サービスからデータを定期収集し、Parquetファイルとして一元管理する。

## 構成

### [Backend (Agent API)](./backend/architecture.md)

LLMが定義済みツールを呼び出して蓄積データにアクセスし、ユーザーの問い合わせに応答する。

- FastAPI + Uvicorn
- DuckDB `:memory:` + httpfs（R2 から直接 Parquet 読み込み）
- DDD (Domain-Driven Design) レイヤードアーキテクチャ
- [Tool System](./backend/tool-system.md) — LLM Tool Use アーキテクチャ
- [Streaming](./backend/streaming.md) — LLM ストリーミングアーキテクチャ

### [Pipelines Service](./pipelines/README.md)

常駐サービス。APScheduler によるスケジュール駆動でデータ収集を実行。

- SQLite で workflow / run / step / lock を管理
- 増分取り込み（カーソルで前回位置を追跡）
- 対応データソース: Spotify / GitHub / Browser History

## 関連ドキュメント

- [システム全体設計](../10.architecture/system-architecture.md)
- [データ戦略](../10.architecture/data-strategy.md)
- [技術スタック一覧](../10.architecture/tech-stack.md)
- [デプロイ手順](../50.deploy/backend.md)
