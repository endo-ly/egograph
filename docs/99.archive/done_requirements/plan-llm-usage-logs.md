# Plan: LLM使用量追跡（llm_usage_logs）

EgoPulse の全 LLM 呼び出し（エージェントループ・セッション要約）において、リクエスト単位のトークン使用量を SQLite の `llm_usage_logs` テーブルに記録する。Microclaw の実装を参考にしつつ、EgoPulse の既存アーキテクチャ（`LlmProvider` trait、`MessagesResponse`、マイグレーション基盤）に適合させる。

> **Note**: 以下の具体的なコード例・API 設計・構成（How）はあくまで参考である。実装時によりよい設計方針があれば積極的に採用すること。

## 設計方針

- **Microclaw の `log_llm_usage` / `get_llm_usage_summary` / `get_llm_usage_by_model` を参考にする** — スキーマ設計、INSERT・集計クエリのパターンを踏襲する
- **Chat Completions API と Responses API の両方の usage フィールドに対応する** — Chat Completions API は `usage.prompt_tokens` / `usage.completion_tokens`、Responses API は `usage.input_tokens` / `usage.output_tokens` とフィールド名が異なる。`OpenAiResponse` と `ResponsesApiResponse` それぞれに usage デシリアライズを追加し、`LlmUsage { input_tokens, output_tokens }` に正規化して統一する
- **ロギングの挿入箇所は2箇所に限定** — エージェントループのメインLLM呼び出し（`agent_loop/turn.rs`）とセッション要約呼び出し（`agent_loop/compaction.rs`）。これらは `request_kind` で区別する
- **usage ロギングの失敗は呼び出し元に影響させない** — `log_llm_usage` が失敗してもエージェントループ全体は継続する（warn ログのみ）。usage 追跡はオブザーバビリティ機能であり、コアフローの信頼性を下げてはならない
- **provider / model 情報は `ResolvedLlmConfig` から取得** — `LlmProvider` trait に provider/model を問い合わせるメソッドを追加し、ログ挿入箇所で利用する
- **コード内のコメント・docstring に外部プロジェクトへの言援をしない** — 「Microclaw 準拠」「参考: Microclaw」等の記述は実装コードに入れない。Plan ドキュメントでのみ言及を許容する

## Plan スコープ

WT作成 → 実装(TDD) → コミット(意味ごとに分離) → PR作成

## 対象一覧

| 対象 | 実装元 |
|---|---|
| `llm_usage_logs` テーブル追加 | Microclaw `db.rs` のスキーマ定義 |
| `log_llm_usage()` / 集計メソッド | Microclaw `db.rs` の同名メソッド |
| `OpenAiResponse` / `ResponsesApiResponse` の usage パース | OpenAI API 仕様（Chat Completions: `prompt_tokens`/`completion_tokens`、Responses: `input_tokens`/`output_tokens`） |
| `LlmUsage` struct + `MessagesResponse` 拡張 | 新規 |
| `LlmProvider` trait への metadata 追加 | 新規 |
| エージェントループへのロギング挿入 | `agent_loop/turn.rs` |
| セッション要約へのロギング挿入 | `agent_loop/compaction.rs` |
| DB スキーマドキュメント更新 | `docs/30.egopulse/db.md` |

---

## Step 0: Worktree 作成

`worktree-create` skill を使用して `feat/142-llm-usage-logs` ブランチの Worktree を作成する。

---

## Step 1: スキーママイグレーション + Storage メソッド (TDD)

前提: なし

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `log_llm_usage_inserts_record` | `log_llm_usage()` を呼び出し、レコードが INSERT されることを確認。`total_tokens = input_tokens + output_tokens` の自動計算、`created_at` が RFC3339 形式であることを検証 |
| `log_llm_usage_returns_row_id` | `log_llm_usage()` が有効な `i64` row ID を返すことを確認 |
| `get_llm_usage_summary_returns_zeros_when_empty` | レコードが存在しない場合、`get_llm_usage_summary(None, None)` が全ゼロのサマリを返す |
| `get_llm_usage_summary_aggregates_all` | 複数レコードを INSERT し、`get_llm_usage_summary(None, None)` が正しい総和を返す |
| `get_llm_usage_summary_filters_by_chat_id` | `get_llm_usage_summary(Some(chat_id), None)` が特定チャットの使用量のみを返す |
| `get_llm_usage_summary_filters_by_since` | `get_llm_usage_summary(None, Some(since_ts))` が期間フィルタで動作する |
| `get_llm_usage_summary_filters_by_chat_id_and_since` | chat_id と since の両方でのフィルタリングが正しい |
| `get_llm_usage_by_model_groups_correctly` | 複数モデルのレコードを INSERT し、`get_llm_usage_by_model()` がモデル別にグループ化された結果を返す |
| `get_llm_usage_by_model_orders_by_total_tokens_desc` | トークン使用量の降順でソートされることを確認 |
| `migration_v2_creates_llm_usage_logs_table` | 新規DBで v2 マイグレーションが適用され、テーブルとインデックスが存在する |
| `migration_v2_applied_on_existing_db` | 既存の v1 DB に対して v2 マイグレーションが適用される |
| `schema_version_increments_to_2` | マイグレーション後の `schema_version()` が 2 を返す |

### GREEN: 実装

1. `SCHEMA_VERSION` を `1` → `2` にインクリメント
2. `run_migrations()` に `if version < 2` ブロックを追加:

```sql
CREATE TABLE IF NOT EXISTS llm_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    caller_channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    request_kind TEXT NOT NULL DEFAULT 'agent_loop',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_chat_created
    ON llm_usage_logs(chat_id, created_at);

CREATE INDEX IF NOT EXISTS idx_llm_usage_created
    ON llm_usage_logs(created_at);
```

3. `storage.rs` に struct とメソッドを追加:

- `LlmUsageSummary { requests, input_tokens, output_tokens, total_tokens, last_request_at }`
- `LlmModelUsageSummary { model, requests, input_tokens, output_tokens, total_tokens }`
- `Database::log_llm_usage(chat_id, caller_channel, provider, model, input_tokens, output_tokens, request_kind) -> Result<i64, StorageError>`
- `Database::get_llm_usage_summary(chat_id: Option<i64>, since: Option<&str>) -> Result<LlmUsageSummary, StorageError>`
- `Database::get_llm_usage_by_model(chat_id: Option<i64>, since: Option<&str>) -> Result<Vec<LlmModelUsageSummary>, StorageError>`

4. `log_llm_usage` 内で `total_tokens = input_tokens.saturating_add(output_tokens)` を計算

### コミット

`feat(storage): add llm_usage_logs table with log and query methods`

---

## Step 2: LLM レスポンスの usage パース (TDD)

前提: なし（Step 1 と並行可能）

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `parse_openai_response_extracts_usage` | Chat Completions API レスポンスの `usage.prompt_tokens` / `usage.completion_tokens` が `MessagesResponse.usage` に `Some(LlmUsage { input_tokens, output_tokens })` としてマッピングされる |
| `parse_openai_response_handles_missing_usage` | `usage` フィールドなしの JSON でもパースが成功し、`usage` が `None` になる |
| `parse_responses_api_extracts_usage` | Responses API レスポンスの `usage.input_tokens` / `usage.output_tokens` が正しく `LlmUsage` にマッピングされる（フィールド名そのまま） |
| `parse_responses_api_handles_missing_usage` | Responses API で `usage` なしでもパースが成功し、`usage` が `None` になる |
| `llm_provider_metadata_returns_config` | `LlmProvider::provider_name()` と `model_name()` が正しい値を返す |

### GREEN: 実装

1. `llm/responses.rs` の `OpenAiResponse` に `usage` フィールドを追加:

```rust
#[derive(Debug, Deserialize)]
pub(crate) struct OpenAiResponse {
    pub(crate) choices: Vec<Choice>,
    #[serde(default)]
    pub(crate) usage: Option<OpenAiUsage>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct OpenAiUsage {
    pub(crate) prompt_tokens: i64,
    pub(crate) completion_tokens: i64,
}
```

2. `llm/responses.rs` の `ResponsesApiResponse` にも `usage` フィールドを追加。Responses API は Chat Completions とフィールド名が異なるため別 struct を定義:

```rust
#[derive(Debug, Deserialize)]
pub(crate) struct ResponsesApiResponse {
    pub(crate) output: Vec<ResponsesOutputItem>,
    #[serde(default)]
    pub(crate) usage: Option<ResponsesApiUsage>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ResponsesApiUsage {
    pub(crate) input_tokens: i64,
    pub(crate) output_tokens: i64,
}
```

3. `llm/mod.rs` に `LlmUsage` struct を追加し、`MessagesResponse` に `usage: Option<LlmUsage>` を追加:

```rust
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LlmUsage {
    pub input_tokens: i64,
    pub output_tokens: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MessagesResponse {
    pub content: String,
    pub tool_calls: Vec<ToolCall>,
    pub usage: Option<LlmUsage>,
}
```

4. `parse_openai_response` で `OpenAiUsage` → `LlmUsage` にマッピング（`prompt_tokens` → `input_tokens`、`completion_tokens` → `output_tokens`）。`parse_responses_response` で `ResponsesApiUsage` → `LlmUsage` にマッピング（フィールド名そのまま）
4. `LlmProvider` trait に metadata メソッドを追加:

```rust
fn provider_name(&self) -> &str;
fn model_name(&self) -> &str;
```

5. `OpenAiProvider` にこれらを実装（`self.model`、固定の `"openai"` 等）
6. テスト用の `FakeProvider` / `RecordingProvider` / `FailingProvider` も `provider_name()` / `model_name()` を実装
7. `MessagesResponse { content, tool_calls }` の既存テストがコンパイルエラーにならないよう `usage: None` を補完

### コミット

`feat(llm): parse usage from OpenAI response and expose provider metadata`

---

## Step 3: エージェントループへの usage ロギング挿入 (TDD)

前提: Step 1, Step 2

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `process_turn_logs_llm_usage_on_agent_loop` | エージェントループのメインLLM呼び出し後、`llm_usage_logs` に `request_kind = "agent_loop"` のレコードが挿入される |
| `process_turn_logs_each_iteration` | ツールループが複数回回った場合、各イテレーションで usage が記録される |
| `compaction_logs_llm_usage_as_summarize` | セッション要約呼び出し後、`llm_usage_logs` に `request_kind = "summarize"` のレコードが挿入される |
| `usage_logging_failure_does_not_break_turn` | `log_llm_usage` が失敗しても `process_turn` は成功する（warn ログのみ） |
| `usage_not_logged_when_response_has_no_usage` | `MessagesResponse.usage` が `None` の場合、ロギングがスキップされる |

### GREEN: 実装

1. `agent_loop/turn.rs` の `process_turn_inner` 内、LLM呼び出し（line 143-152）の直後に usage ロギングを追加:

```rust
// After `let response = channel_llm.send_message(...).await?;`
if let Some(usage) = &response.usage {
    let db = Arc::clone(&state.db);
    let channel = context.channel.clone();
    let provider = channel_llm.provider_name().to_string();
    let model = channel_llm.model_name().to_string();
    let input_tokens = usage.input_tokens;
    let output_tokens = usage.output_tokens;
    let _ = call_blocking(db, move |db| {
        db.log_llm_usage(chat_id, &channel, &provider, &model, input_tokens, output_tokens, "agent_loop")
    }).await.map_err(|e| warn!(error = %e, "llm usage logging failed"));
}
```

2. `agent_loop/compaction.rs` の `summarize_and_compact` 内、要約LLM呼び出し（line 79-83）の直後に usage ロギングを追加。`request_kind = "summarize"` を使用。

3. 両箇所とも `call_blocking` の結果を `_` で受け、エラー時は `warn!` のみ。

### コミット

`feat(agent-loop): insert LLM usage logging in agent loop and compaction`

---

## Step 4: ドキュメント更新

前提: Step 1-3

### 実装

1. `docs/30.egopulse/db.md` に以下を追加:
   - ER 図に `llm_usage_logs` を追加
   - テーブル定義セクションに `llm_usage_logs` を追加（カラム説明・操作一覧）
   - Rust 構造体マッピングに `LlmUsageSummary`, `LlmModelUsageSummary` を追加
   - マイグレーション手順の説明を更新（v1 → v2）
   - Microclaw との差分サマリを更新

### コミット

`docs(egopulse): update db.md with llm_usage_logs schema`

---

## Step 5: 動作確認

- `cargo test -p egopulse` — 全テスト通過
- `cargo fmt --check` — フォーマット違反なし
- `cargo clippy --all-targets --all-features -- -D warnings` — Clippy 警告なし
- `cargo check -p egopulse` — コンパイルエラーなし

---

## Step 6: PR 作成

- ブランチ: `feat/142-llm-usage-logs`
- タイトル: `feat: LLM使用量追跡（llm_usage_logs）`
- 本文に `Close #142` を明記
- `pr-review-back-workflow` skill でレビュー対応

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `egopulse/src/storage.rs` | 変更 | v2 マイグレーション追加、`LlmUsageSummary`/`LlmModelUsageSummary` struct 追加、`log_llm_usage`/`get_llm_usage_summary`/`get_llm_usage_by_model` メソッド追加 |
| `egopulse/src/llm/mod.rs` | 変更 | `LlmUsage` struct 追加、`MessagesResponse` に `usage` フィールド追加、`LlmProvider` trait に `provider_name`/`model_name` 追加 |
| `egopulse/src/llm/responses.rs` | 変更 | `OpenAiResponse` に `usage` フィールド追加、`OpenAiUsage` struct 追加、`parse_openai_response` で usage マッピング |
| `egopulse/src/llm/openai.rs` | 変更 | `OpenAiProvider` に `provider_name`/`model_name` 実装 |
| `egopulse/src/agent_loop/turn.rs` | 変更 | エージェントループの LLM 呼び出し直後に usage ロギング追加、テストプロバイダーの `provider_name`/`model_name` 実装 |
| `egopulse/src/agent_loop/compaction.rs` | 変更 | セッション要約 LLM 呼び出し直後に usage ロギング追加 |
| `docs/30.egopulse/db.md` | 変更 | スキーマドキュメント更新 |

---

## コミット分割

1. `feat(storage): add llm_usage_logs table with log and query methods`
2. `feat(llm): parse usage from OpenAI response and expose provider metadata`
3. `feat(agent-loop): insert LLM usage logging in agent loop and compaction`
4. `docs(egopulse): update db.md with llm_usage_logs schema`

---

## テストケース一覧（全 23 件）

### Storage: llm_usage_logs (12)

1. `log_llm_usage_inserts_record` — レコードの INSERT と total_tokens の自動計算を確認
2. `log_llm_usage_returns_row_id` — row ID の返却を確認
3. `get_llm_usage_summary_returns_zeros_when_empty` — 空テーブルで全ゼロサマリ
4. `get_llm_usage_summary_aggregates_all` — 全レコードの総和集計
5. `get_llm_usage_summary_filters_by_chat_id` — chat_id フィルタ
6. `get_llm_usage_summary_filters_by_since` — since フィルタ
7. `get_llm_usage_summary_filters_by_chat_id_and_since` — 複合フィルタ
8. `get_llm_usage_by_model_groups_correctly` — モデル別グループ化
9. `get_llm_usage_by_model_orders_by_total_tokens_desc` — 降順ソート
10. `migration_v2_creates_llm_usage_logs_table` — 新規DBでのテーブル作成
11. `migration_v2_applied_on_existing_db` — 既存DBへのマイグレーション
12. `schema_version_increments_to_2` — バージョン番号の更新

### LLM: usage パース + provider metadata (5)

13. `parse_openai_response_extracts_usage` — Chat Completions API の usage パース（`prompt_tokens`/`completion_tokens` → `input_tokens`/`output_tokens` マッピング）
14. `parse_openai_response_handles_missing_usage` — usage フィールドなしのケース
15. `parse_responses_api_extracts_usage` — Responses API の usage パース（`input_tokens`/`output_tokens` そのまま）
16. `parse_responses_api_handles_missing_usage` — Responses API で usage なし
17. `llm_provider_metadata_returns_config` — provider_name/model_name の返却

### Agent Loop: usage ロギング (5)

18. `process_turn_logs_llm_usage_on_agent_loop` — メインループのロギング
19. `process_turn_logs_each_iteration` — 複数イテレーションのロギング
20. `compaction_logs_llm_usage_as_summarize` — 要約時のロギング
21. `usage_logging_failure_does_not_break_turn` — ロギング失敗の非影響
22. `usage_not_logged_when_response_has_no_usage` — usage なし時のスキップ

### Docs (0)

※ ドキュメント更新にテストなし

---

## 工数見積もり

| Step | 内容 | 見積もり |
|---|---|---|
| Step 0 | Worktree 作成 | ~10 行 |
| Step 1 | スキーママイグレーション + Storage メソッド（テスト含む） | ~250 行 |
| Step 2 | LLM レスポンス usage パース（テスト含む） | ~140 行 |
| Step 3 | エージェントループ ロギング挿入（テスト含む） | ~150 行 |
| Step 4 | ドキュメント更新 | ~80 行 |
| **合計** | | **~630 行** |
