# Plan: EgoPulse SecretRef 導入

OpenClaw 風の SecretRef オブジェクトを導入し、設定ファイル内の秘密情報を環境変数・コマンド実行から解決する。リテラル値は後方互換として残す。

> **Note**: 以下の具体的なコード例・API 設計・構成（How）はあくまで参考である。実装時によりよい設計方針があれば各自で判断し採用する。

## 設計方針

- OpenClaw SecretRef 形式を採用: `{ source: "env"|"exec", id: "VAR_NAME" }` / `{ source: "exec", command: "cmd args" }`
- `provider` 概念は導入しない。exec モードは SecretRef に直接コマンドを書く（簡略化）
- リテラル文字列値はそのまま動作（後方互換）。YAML で文字列 OR SecretRef オブジェクトを受け付ける
- 全文字列フィールドで SecretRef を利用可能（api_key, auth_token, bot_token, base_url 等）
- env モードの解決順: `process env → ~/.egopulse/.env`
- EgoPulse 起動時に `~/.egopulse/.env` を自動読込
- setup/save 時は SecretRef を YAML に書き、実際の値を `.env` に保存

### 出自の保持（Critical: 設計破綻防止）

Config の実行時型は「値の出自」を保持し、save 時に元の SecretRef を復元できるようにする:

```rust
/// 解決済みの文字列値とその出自。
#[derive(Clone, Debug)]
pub(crate) enum ResolvedValue {
    /// リテラル値（YAML に文字列として書き戻す）
    Literal(String),
    /// env SecretRef から解決（YAML に SecretRef として書き戻す）
    EnvRef { value: String, id: String },
    /// exec SecretRef から解決（YAML に SecretRef として書き戻す）
    ExecRef { value: String, command: String },
}
```

`ProviderConfig.api_key`, `ChannelConfig.auth_token`, `ChannelConfig.bot_token` 等の秘密フィールドは
内部的に `Option<ResolvedValue>` を保持する。これにより:
- 実行時は `.value()` で実際の値を取得
- save 時は `.to_yaml_value()` で元の SecretRef 構造またはリテラルを復元
- Web UI 経由の save でも、exec ref が .env に上書きされる事故を防止

### SecretRef 解決と env override の分離（Critical: 優先順位破綻防止）

SecretRef 解決と既存の process env override は**別レイヤー**として明確に分離する:

1. **Layer 1: YAML SecretRef 解決** — `{ source: env, id: X }` を process env / .env から解決
2. **Layer 2: process env override** — `EGOPULSE_WEB_HOST` 等が Layer 1 の結果を上書き

`.env` ファイルのキーは SecretRef の `id` と同一（`OPENAI_API_KEY`, `EGOPULSE_WEB_AUTH_TOKEN` 等）。
Layer 2 の override キーと重複するが、**意味論は異なる**:
- SecretRef `id`: YAML 内の `{ source: env, id: X }` が参照する値の保存先
- process env override: 実行時に YAML 値を上書きする一時的な値

setup wizard が書き出す `.env` は SecretRef の `id` と一致するキーを使用する。

## Plan スコープ

WT作成 → 実装(TDD) → コミット(意味ごとに分離) → PR作成

## YAML 記法例

```yaml
providers:
  openai:
    label: OpenAI
    base_url: https://api.openai.com/v1
    api_key:
      source: env
      id: OPENAI_API_KEY
    default_model: gpt-4o-mini

channels:
  discord:
    enabled: true
    bot_token:
      source: exec
      command: "pass show discord/bot_token"

# リテラル値もそのまま動く
channels:
  web:
    enabled: true
    port: 10961
    auth_token: my-static-token
```

## 対象一覧

| 対象 | 実装元 |
|---|---|
| SecretRef 型定義 + resolver | `egopulse/src/config/secret_ref.rs`（新規） |
| loader での SecretRef 解決 + .env 読込 | `egopulse/src/config/loader.rs` |
| 型定義更新（String → StringOrRef） | `egopulse/src/config/mod.rs` |
| persist での SecretRef 保存 + .env 書込 | `egopulse/src/config/persist.rs` |
| setup 保存の SecretRef 化 | `egopulse/src/setup/summary.rs` |
| Web UI の SecretRef 対応 | `egopulse/src/web/config.rs` |
| エラー型追加 | `egopulse/src/error.rs` |
| runtime 警告メッセージ更新 | `egopulse/src/runtime.rs` |
| ドキュメント更新 | `docs/30.egopulse/config.md` |

---

## Step 0: Worktree 作成

- `worktree-create` スキルを使い `fix/secret-env-migration` ブランチで worktree 作成済み。

---

## Step 1: SecretRef 型と Resolver (TDD)

### 型定義

`secret_ref.rs` に以下を定義:

```rust
/// 設定ファイル内の秘密参照。
///
/// - env モード: `{ source: "env", id: "OPENAI_API_KEY" }`
/// - exec モード: `{ source: "exec", command: "pass show ..." }`
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub(crate) enum SecretRef {
    Ref {
        source: SecretSource,
        #[serde(skip_serializing_if = "Option::is_none")]
        id: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        command: Option<String>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub(crate) enum SecretSource {
    Env,
    Exec,
}
```

YAML フィールドは `String` OR `SecretRef` OR `null` を受け付ける:
```rust
// serde(untagged) で文字列と SecretRef を自動判別
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub(crate) enum StringOrRef {
    Literal(String),
    Ref(SecretRef),
}
```

### Resolver

- `resolve_secret_ref(ref: &SecretRef, dotenv: &HashMap<String, String>) -> Result<String, ConfigError>`
- env モード: `std::env::var(id)` → `dotenv.get(id)` → エラー
- exec モード: `std::process::Command` で command を実行 → stdout（trim）を返す。タイムアウト 10 秒
- `.env` リーダー: `read_dotenv(path) -> HashMap<String, String>`。外部 crate なし

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `secret_ref_env_resolves_from_process_env` | env モードが process env から解決 |
| `secret_ref_env_resolves_from_dotenv` | env モードが .env から解決 |
| `secret_ref_env_prefers_process_env_over_dotenv` | process env 優先 |
| `secret_ref_env_unresolved_returns_error` | 解決不能時はエラー |
| `secret_ref_exec_captures_stdout` | exec モードが stdout を取得 |
| `secret_ref_exec_trims_output` | 出力の trim |
| `secret_ref_exec_failure_returns_error` | コマンド失敗時はエラー |
| `secret_ref_literal_value_unchanged` | リテラル値はそのまま |

### GREEN: 実装

- `secret_ref.rs` 新規作成
- `error.rs` に `SecretRefUnresolved`, `SecretRefExecFailed` 追加
- `mod.rs` に `secret_ref` モジュール登録
- `mod.rs` のテストモジュールにテスト追加

### コミット

`feat(egopulse): add SecretRef type and resolver`

---

## Step 2: Loader への統合 (TDD)

### 変更概要

- `loader.rs` の `FileProviderConfig`, `FileChannelConfig` の該当フィールドを `Option<StringOrRef>` に変更
- `build_config()` 内で .env を読み込み、各 `StringOrRef` を解決して `String` に変換
- 既存の process env override（`EGOPULSE_WEB_HOST` 等）は SecretRef 解決後に適用

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `load_resolves_provider_api_key_from_env_ref` | `api_key: { source: env, id: OPENAI_API_KEY }` が解決される |
| `load_resolves_channel_bot_token_from_exec_ref` | `bot_token: { source: exec, command: echo test }` が解決される |
| `load_literal_api_key_works_as_before` | `api_key: sk-literal` がそのまま動く |
| `load_mixed_literal_and_ref_in_same_config` | リテラルと SecretRef が混在して動く |

### GREEN: 実装

- `loader.rs` の内部型（`FileProviderConfig`, `FileChannelConfig`）の文字列フィールドを `Option<StringOrRef>` 化
- `resolve_string_or_ref(value: Option<StringOrRef>, dotenv) -> Result<Option<String>>` ヘルパー追加
- 各 normalize 関数で resolver を呼び出す

### コミット

`feat(egopulse): integrate SecretRef resolution into config loader`

---

## Step 3: Persist での SecretRef 保存と .env 書込 (TDD)

### 変更概要

- `persist.rs` の `SerializableProvider` / `SerializableChannel` が SecretRef 形式で YAML に書き出す
- setup/save 時、既存のリテラル秘密値を SecretRef（env モード）に変換して保存
- 実際の値は `~/.egopulse/.env` に 0600 で書き込む
- `.env` は既存キーを保持しつつ更新

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `save_writes_env_ref_to_yaml_and_value_to_dotenv` | 保存後 YAML に SecretRef、.env に実際の値 |
| `save_dotenv_preserves_unrelated_keys` | 既存 .env の無関係キーを保持 |
| `save_dotenv_creates_with_0600_permissions` | .env が 0600 権限で作成される |
| `roundtrip_migrates_literal_to_env_ref` | リテラル値を load → save で SecretRef 化 |
| `save_config_with_secrets_updates_summary_message` | 保存完了メッセージに .env 情報を含む |

### GREEN: 実装

- `persist.rs` に `save_config_with_secrets(config, yaml_path)` 追加
- `save_dotenv(config, dotenv_path)` 追加
- `SerializableProvider.api_key` → SecretRef（env モード、`{PROVIDER_ID}_API_KEY`）
- `SerializableChannel.auth_token` → SecretRef（env モード、`EGOPULSE_WEB_AUTH_TOKEN`）
- `SerializableChannel.bot_token` → SecretRef（env モード、`EGOPULSE_{CHANNEL}_BOT_TOKEN`）
- `summary.rs` で `save_config_with_secrets` を使用
- `web/config.rs` で `save_config_with_secrets` を使用

### コミット

`feat(egopulse): persist secrets as SecretRef in yaml with .env values`

---

## Step 4: Runtime 文言とドキュメント整合

### 変更概要

- `runtime.rs` の Discord/Telegram トークン不足警告を更新
- `docs/30.egopulse/config.md` を SecretRef 形式に更新

### コミット

`docs(egopulse): document SecretRef system in config spec`

---

## Step 5: 動作確認

- `cd egopulse && cargo test -p egopulse`
- `cd egopulse && cargo fmt --check`
- `cd egopulse && cargo check -p egopulse`
- `cd egopulse && cargo clippy --all-targets --all-features -- -D warnings`

---

## Step 6: PR 更新

- 既存 PR #163 を force push で更新
- PR description を SecretRef 方針に書き直し

---

## テストケース一覧（全 17 件）

### SecretRef Resolver (8)
1. `secret_ref_env_resolves_from_process_env`
2. `secret_ref_env_resolves_from_dotenv`
3. `secret_ref_env_prefers_process_env_over_dotenv`
4. `secret_ref_env_unresolved_returns_error`
5. `secret_ref_exec_captures_stdout`
6. `secret_ref_exec_trims_output`
7. `secret_ref_exec_failure_returns_error`
8. `secret_ref_literal_value_unchanged`

### Loader 統合 (4)
9. `load_resolves_provider_api_key_from_env_ref`
10. `load_resolves_channel_bot_token_from_exec_ref`
11. `load_literal_api_key_works_as_before`
12. `load_mixed_literal_and_ref_in_same_config`

### Persist / Setup (5)
13. `save_writes_env_ref_to_yaml_and_value_to_dotenv`
14. `save_dotenv_preserves_unrelated_keys`
15. `save_dotenv_creates_with_0600_permissions`
16. `roundtrip_migrates_literal_to_env_ref`
17. `save_config_with_secrets_updates_summary_message`

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `egopulse/src/config/secret_ref.rs` | **新規** | SecretRef 型、resolver、.env パーサ |
| `egopulse/src/config/loader.rs` | 変更 | StringOrRef 対応、.env 読込、resolve 統合 |
| `egopulse/src/config/persist.rs` | 変更 | SecretRef 保存、.env 書込、0600 権限 |
| `egopulse/src/config/resolve.rs` | 変更 | `save_config_with_secrets` 追加 |
| `egopulse/src/config/mod.rs` | 変更 | モジュール登録、テスト追加 |
| `egopulse/src/error.rs` | 変更 | `SecretRefUnresolved`, `SecretRefExecFailed` 追加 |
| `egopulse/src/setup/summary.rs` | 変更 | `save_config_with_secrets` 使用 |
| `egopulse/src/web/config.rs` | 変更 | `save_config_with_secrets` 使用 |
| `egopulse/src/runtime.rs` | 変更 | 警告メッセージ更新 |
| `docs/30.egopulse/config.md` | 変更 | SecretRef ドキュメント |
| `docs/30.egopulse/plan-secret-env-migration.md` | 変更 | 本プラン更新 |

---

## コミット分割

1. `feat(egopulse): add SecretRef type and resolver`
2. `feat(egopulse): integrate SecretRef resolution into config loader`
3. `feat(egopulse): persist secrets as SecretRef in yaml with .env values`
4. `docs(egopulse): document SecretRef system in config spec`

---

## 工数見積もり

| Step | 内容 | 見積もり |
|---|---|---|
| Step 1 | SecretRef 型 + resolver + テスト | ~150 行 |
| Step 2 | loader 統合 + テスト | ~120 行 |
| Step 3 | persist + setup + web + テスト | ~200 行 |
| Step 4 | runtime + docs | ~80 行 |
| Step 5 | 動作確認 | ~10 行 |
| Step 6 | PR 更新 | ~10 行 |
| **合計** |  | **~570 行** |
