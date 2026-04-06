# EgoPulse

AIエージェントランタイム。LLMが EgoGraph の蓄積データにツール経由でアクセスし、個人の文脈に基づいた回答を返す。

## 概要

- **マルチチャネル** — TUI / Web UI（React + SSE + WebSocket）/ Discord / Telegram を単一バイナリで提供
- **永続セッション** — SQLite で会話履歴を管理。セッションの再開・切り替えに対応
- **OpenAI 互換** — OpenAI、OpenRouter、Ollama、ローカル LLM など幅広く対応
- **セットアップウィザード** — `egopulse setup` で対話型 TUI から初期設定
- **systemd 統合** — `egopulse gateway install` で本番サーバーにデプロイ
- **Rust 製** — Tokio 非同期ランタイムで軽量・高速に動作

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| 言語 | Rust (edition 2024) |
| 非同期ランタイム | Tokio |
| TUI | Ratatui + crossterm |
| Web UI | Axum + React/Vite (include_dir! 埋め込み) |
| Discord | Serenity 0.12 |
| Telegram | Teloxide 0.17 |
| DB | rusqlite (SQLite) |
| HTTP | reqwest |
| CLI | clap |

## 関連ドキュメント

- [システム全体設計](../10.architecture/system-architecture.md)
- [技術スタック一覧](../10.architecture/tech-stack.md)
- [デプロイ手順](../50.deploy/egopulse.md)
