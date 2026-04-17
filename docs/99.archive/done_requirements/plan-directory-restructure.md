# Plan: EgoPulse ディレクトリ構造リファクタリング

`Config.data_dir` を `Config.state_root` にリネームし、デフォルトを `~/.egopulse` に変更。全モジュールのパス参照を `state_root` から派生する構成に統一し、TOBE ディレクトリ仕様（`directory.md`）との整合を取る。

> **Note**: 以下の具体的なコード例・API 設計・構成（How）はあくまで参考である。実装時によりよい設計方針があれば積極的に採用すること。

## 設計方針

- **YAML パス露出は `state_root` のみ**。内部ディレクトリ（`runtime/`, `workspace/`, `skills/`, `groups/` 等）は全てハードコードで派生。Microclaw の `data_dir` パターンを踏襲。
- **`state_root` = `~/.egopulse`**。旧 `data_dir`（`~/.egopulse/data/`）の `/data` を削除し、ルートそのものを指す。
- **`runtime_dir()` 導入**: DB・assets・groups・status.json を `state_root/runtime/` に集約。旧コードでは `data_dir` 直下に散在していた。
- **組み込みスキルはスキャンのみ実装**: `state_root/skills/` から読み込む2層スキル構造（組み込み + ユーザー）のスキャンロジックを追加する。スキルファイルの配置（配布・初期化）は別スコープ。
- **後方互換は一切しない**: `data_dir` YAMLキー・`default_data_dir()` 関数は完全削除。alias も入れない。リポジトリ規約「互換分岐を追加しない」に従う。

## Plan スコープ

WT作成 → 実装(TDD) → コミット(意味ごとに分離) → PR作成

## 対象一覧

| 対象 | ファイル | 変更概要 |
|---|---|---|
| Config 中核 | `config.rs` | `data_dir` → `state_root` リネーム、`runtime_dir()` 等の派生アクセサ追加、デフォルト値変更、**FileConfig / SerializableConfig / Web payload の読み書き全てを同一Stepで `state_root` に一本化** |
| ストレージ | `storage.rs` | DBパスを `runtime_dir()/egopulse.db` に変更 |
| アセット | `assets.rs` | assets パスを `runtime_dir()/assets` に変更 |
| コンパクション | `agent_loop/compaction.rs` | archive パスを `runtime_dir()/groups/` に変更 |
| ステータス | `status.rs` | status.json を `runtime_dir()/` に変更 |
| MCP | `mcp.rs` | `default_state_root()` 参照を `Config` 経由に統一 |
| スキル | `skills.rs` | `state_root/skills/` スキャン追加（組み込みスキル） |
| ランタイム | `runtime.rs` | `write_status` 呼び出しパス修正 |
| Web Config API | `web/config.rs` | `data_dir` → `state_root` フィールド名更新 |
| ツールレジストリ | `tools/mod.rs` | テスト内 `data_dir` 参照修正 |
| セッション/ターン | `agent_loop/session.rs`, `agent_loop/turn.rs` | テスト内 `data_dir` 参照修正 |
| セットアップ | `setup/summary.rs` | `default_data_dir()` → `default_state_root()` に変更 |
| ドキュメント | `docs/30.egopulse/directory.md` | 実装後の整合確認（内容は既にTOBEなので変更不要の可能性） |
| Example config | `egopulse.config.example.yaml` | `data_dir` コメントがあれば `state_root` に更新 |

---

## Step 0: Worktree 作成

```bash
# skill: worktree-create を使用
# ブランチ: refactor/egopulse-directory-restructure
```

---

## Step 1: Config 中核 — `data_dir` → `state_root` 完全リネームと派生アクセサ (TDD)

前提: なし（最初の Step）

**重要**: この Step で Config の読み込み・保存・Web payload・セットアップ生成の **round-trip 全て** を `state_root` に一本化する。中途半端な状態でコミットしないこと。

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_default_state_root_is_home_egopulse` | `default_state_root()` が `~/.egopulse` を返す |
| `test_runtime_dir_is_state_root_runtime` | `config.runtime_dir()` が `state_root/runtime` を返す |
| `test_workspace_dir_is_state_root_workspace` | `config.workspace_dir()` が `state_root/workspace` を返す |
| `test_skills_dir_is_state_root_skills` | `config.skills_dir()` が `state_root/skills` を返す |
| `test_user_skills_dir_is_workspace_skills` | `config.user_skills_dir()` が `state_root/workspace/skills` を返す |
| `test_db_path_is_runtime_egopulse_db` | `config.db_path()` が `runtime_dir()/egopulse.db` を返す |
| `test_assets_dir_is_runtime_assets` | `config.assets_dir()` が `runtime_dir()/assets` を返す |
| `test_groups_dir_is_runtime_groups` | `config.groups_dir()` が `runtime_dir()/groups` を返す |
| `test_status_json_path_is_runtime_status_json` | `config.status_json_path()` が `runtime_dir()/status.json` を返す |
| `test_config_debug_shows_state_root` | `Debug` 出力に `state_root` が含まれること |
| `test_config_yaml_roundtrip_uses_state_root` | YAML書き込み・読み込みが `state_root` キーで往復できること |
| `test_config_load_rejects_data_dir_key` | YAML 内の `data_dir` キーは未知フィールドとして無視されること（aliasなし） |

### GREEN: 実装

以下を **全て同時** に変更する:

1. **`Config` 構造体**: `pub data_dir: String` → `pub state_root: String`
2. **`default_data_dir()`**: 削除。`default_state_root()` が唯一のパス生成関数
3. **派生アクセサ追加**:
   - `runtime_dir()`, `workspace_dir()`, `skills_dir()`, `user_skills_dir()`
   - `db_path()`, `assets_dir()`, `groups_dir()`, `status_json_path()`
4. **`FileConfig`（デシリアライズ用）**: フィールドが存在しないので変更なし（現状 `data_dir` フィールドを持たない）
5. **`SerializableConfig`（シリアライズ用）**: `data_dir` フィールドを `state_root` にリネーム
6. **`build_config()` 内**: `let data_dir = default_data_dir()(...)` → `let state_root = default_state_root()(...).to_string_lossy().into_owned()`
7. **`web/config.rs` `ConfigPayload`**: `data_dir` → `state_root` にリネーム、`default_payload()` と `payload_from_config()` も追従
8. **`setup/summary.rs`**: `default_data_dir()` 呼び出し → `default_state_root()` に変更、`Config` 構築の `data_dir` → `state_root` も変更
9. **全テストヘルパー**（`tools/mod.rs`, `agent_loop/session.rs`, `agent_loop/turn.rs`, `compaction.rs`）: `data_dir` → `state_root` にリネーム
10. **`default_data_dir()` の `use` 文**: `config.rs` テスト、`setup/summary.rs` から削除

**alias は入れない**。`data_dir` YAMLキーは未知フィールドとしてserdeのdeny-unknown-fields（または無視）で処理される。

### コミット

`refactor: rename Config.data_dir to state_root with full round-trip update`

---

## Step 2: Storage — DB パスを runtime_dir に移動 (TDD)

前提: Step 1

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_database_creates_runtime_dir` | `Database::new` が `runtime/` ディレクトリを作成すること |
| `test_database_path_under_runtime` | DBファイルが `{state_root}/runtime/egopulse.db` に作成されること |

### GREEN: 実装

- `storage.rs` の `Database::new()` の引数を `data_dir: &str` → `state_root: &str` に変更
- 内部で `Path::new(state_root).join("runtime").join("egopulse.db")` を使用
- `create_dir_all` で `runtime/` を作成

### コミット

`refactor: move database path to state_root/runtime/egopulse.db`

---

## Step 3: Assets — assets パスを runtime_dir に移動 (TDD)

前提: Step 1

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_asset_store_root_is_runtime_assets` | `AssetStore::new` が `{state_root}/runtime/assets` をルートにする |
| `test_asset_store_creates_images_dir` | `images/` ディレクトリが作成されること |

### GREEN: 実装

- `assets.rs` の `AssetStore::new()` の引数を `data_dir: &str` → `state_root: &str` に変更
- 内部で `Path::new(state_root).join("runtime").join("assets")` を使用

### コミット

`refactor: move assets path to state_root/runtime/assets`

---

## Step 4: Compaction — archive パスを runtime_dir/groups に移動 (TDD)

前提: Step 1

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_archive_dir_under_runtime_groups` | アーカイブディレクトリが `{state_root}/runtime/groups/{channel}/{chat_id}/conversations` になること |

### GREEN: 実装

- `compaction.rs` の `archive_conversation_blocking()` で `PathBuf::from(data_dir).join("groups")` → `PathBuf::from(state_root).join("runtime").join("groups")` に変更
- 引数名を `data_dir` → `state_root` に変更
- 呼び出し側（`archive_conversation()`）も追従

### コミット

`refactor: move conversation archive path to state_root/runtime/groups`

---

## Step 5: Status — status.json を runtime_dir に移動 (TDD)

前提: Step 1

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_write_status_under_runtime` | `write_status` が `{state_root}/runtime/status.json` に書き込むこと |
| `test_read_status_under_runtime` | `read_status` が `{state_root}/runtime/status.json` から読むこと |

### GREEN: 実装

- `status.rs` の `write_status()` と `read_status()` で `state_root.join(STATUS_FILE)` → `state_root.join("runtime").join(STATUS_FILE)` に変更
- `write_status` 呼び出し前に `create_dir_all(state_root.join("runtime"))` を追加

### コミット

`refactor: move status.json to state_root/runtime/`

---

## Step 6: MCP — state_root 参照の統一 (TDD)

前提: Step 1

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_mcp_config_paths_uses_state_root` | `mcp_config_paths` が state_root 直下の `mcp.json`, `mcp.d` を返すこと |

### GREEN: 実装

- `mcp.rs` の `mcp_config_paths()` 内 `let state_root = default_state_root()?` を変更せず（既に `state_root` 直下に `mcp.json` を配置しているため、ロジックは正しい）
- 関数シグネチャや引数名を確認し、`state_root` という名称で統一されているか確認

### コミット

`refactor: align MCP path references with state_root naming`

---

## Step 7: Skills — 組み込みスキルスキャン追加 (TDD)

前提: Step 1

**スコープ**: `state_root/skills/` からスキルを読み込むスキャンロジックの追加のみ。スキルファイルの配布・初期化（バイナリへの同梱や初回展開）は別スコープ。

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_discover_builtin_skills` | `state_root/skills/` 配下のスキルが発見されること |
| `test_user_skills_override_builtin` | `state_root/workspace/skills/` に同名スキルがある場合、ユーザー側が優先されること |
| `test_discover_both_skill_dirs` | 組み込みとユーザーの両方がスキャンされること |
| `test_builtin_skills_empty_dir_graceful` | `state_root/skills/` が存在しなくてもエラーにならないこと |

### GREEN: 実装

- `skills.rs` の `SkillManager::from_skills_dir()` に組み込みスキルディレクトリ（`state_root/skills/`）のスキャンを追加
- `discover_skill_dirs()` のロジック:
  1. 最高優先度: `state_root/workspace/skills/*`（ユーザースキル）
  2. 次に: `state_root/skills/*`（組み込みスキル）
- 現在のコンストラクタ引数が `skills_dir` のみなので、`state_root` も受け取るようシグネチャ変更が必要

### コミット

`feat: add built-in skills scanning from state_root/skills`

---

## Step 8: Runtime — 呼び出し側の追従 (TDD)

前提: Step 1-7

### RED: テスト先行

| テストケース | 内容 |
|---|---|
| `test_build_app_state_uses_runtime_dir` | `build_app_state` が `runtime_dir()` 経由でDB/assetsを初期化すること |

### GREEN: 実装

- `runtime.rs`: `Database::new(&config.data_dir)` → `Database::new(&config.state_root)` に変更
- `runtime.rs`: `AssetStore::new(&config.data_dir)` → `AssetStore::new(&config.state_root)` に変更
- `runtime.rs`: `write_status` 呼び出しで `default_state_root()` ではなく `config.state_root` を使用
- `tools/mod.rs` テスト: `data_dir` → `state_root` に追従
- `agent_loop/session.rs` テスト: `data_dir` → `state_root` に追従
- `agent_loop/turn.rs` テスト: `data_dir` → `state_root` に追従
- `gateway.rs`: テスト内ハードコードパスの確認（`/home/user/.egopulse/` は変わらないので多分そのまま）

### コミット

`refactor: update all callers to use state_root and derived paths`

---

## Step 9: 最終掃除 — 例示設定・docstring・コメント

前提: Step 8

### RED: テスト先行

特になし（リグレッション確認のみ）

### GREEN: 実装

- `egopulse.config.example.yaml`: `data_dir` フィールドがあれば `state_root` に変更（現状では同フィールドがないので多分変更不要）
- `config.rs` 内 docstring で `data_dir` を参照している箇所があれば `state_root` に更新
- `storage.rs`, `assets.rs` の docstring で `{data_dir}/...` となっている箇所を更新
- `default_data_dir()` 関数が残っていれば削除

### コミット

`chore: clean up remaining data_dir references in docs and comments`

---

## Step 10: 動作確認

```bash
# Rust チェック
cargo fmt --check -p egopulse
cargo check -p egopulse
cargo clippy --all-targets --all-features -- -D warnings
cargo test -p egopulse
```

---

## Step 11: PR 作成

```bash
gh pr create --title "refactor: align egopulse directory structure with TOBE spec" --body "..."
```

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `egopulse/src/config.rs` | 変更 | `data_dir` → `state_root` リネーム、派生アクセサ追加、デフォルト値変更、SerializableConfig/Web payload 同時更新 |
| `egopulse/src/storage.rs` | 変更 | DBパスを `runtime/` 下に変更 |
| `egopulse/src/assets.rs` | 変更 | assets パスを `runtime/` 下に変更 |
| `egopulse/src/agent_loop/compaction.rs` | 変更 | archive パスを `runtime/groups/` に変更 |
| `egopulse/src/status.rs` | 変更 | status.json を `runtime/` 下に変更 |
| `egopulse/src/mcp.rs` | 変更 | 参照名の統一 |
| `egopulse/src/skills.rs` | 変更 | 組み込みスキルスキャン追加 |
| `egopulse/src/runtime.rs` | 変更 | 呼び出しパス追従 |
| `egopulse/src/web/config.rs` | 変更 | フィールド名追従 |
| `egopulse/src/setup/summary.rs` | 変更 | `default_data_dir()` → `default_state_root()` |
| `egopulse/src/tools/mod.rs` | 変更 | テスト内参照追従 |
| `egopulse/src/agent_loop/session.rs` | 変更 | テスト内参照追従 |
| `egopulse/src/agent_loop/turn.rs` | 変更 | テスト内参照追従 |
| `egopulse/src/gateway.rs` | 変更 | テスト内参照確認 |
| `egopulse/egopulse.config.example.yaml` | 変更 | フィールド名更新（必要な場合） |

---

## コミット分割

1. `refactor: rename Config.data_dir to state_root with full round-trip update`
2. `refactor: move database path to state_root/runtime/egopulse.db`
3. `refactor: move assets path to state_root/runtime/assets`
4. `refactor: move conversation archive path to state_root/runtime/groups`
5. `refactor: move status.json to state_root/runtime/`
6. `refactor: align MCP path references with state_root naming`
7. `feat: add built-in skills scanning from state_root/skills`
8. `refactor: update all callers to use state_root and derived paths`
9. `chore: clean up remaining data_dir references in docs and comments`

---

## テストケース一覧（全 27 件）

### Config (12)
1. `test_default_state_root_is_home_egopulse` — デフォルトが `~/.egopulse` を返す
2. `test_runtime_dir_is_state_root_runtime` — `runtime_dir()` が正しく派生
3. `test_workspace_dir_is_state_root_workspace` — `workspace_dir()` が正しく派生
4. `test_skills_dir_is_state_root_skills` — `skills_dir()` が正しく派生
5. `test_user_skills_dir_is_workspace_skills` — `user_skills_dir()` が正しく派生
6. `test_db_path_is_runtime_egopulse_db` — `db_path()` が正しく派生
7. `test_assets_dir_is_runtime_assets` — `assets_dir()` が正しく派生
8. `test_groups_dir_is_runtime_groups` — `groups_dir()` が正しく派生
9. `test_status_json_path_is_runtime_status_json` — `status_json_path()` が正しく派生
10. `test_config_debug_shows_state_root` — Debug 出力に state_root が含まれる
11. `test_config_yaml_roundtrip_uses_state_root` — YAML書き込み・読み込みが state_root キーで往復
12. `test_config_load_rejects_data_dir_key` — YAML 内の data_dir キーは未知フィールドとして無視

### Storage (2)
13. `test_database_creates_runtime_dir` — runtime/ ディレクトリが自動作成される
14. `test_database_path_under_runtime` — DBファイルパスが runtime/ 下

### Assets (2)
15. `test_asset_store_root_is_runtime_assets` — AssetStore ルートが runtime/assets
16. `test_asset_store_creates_images_dir` — images/ が自動作成される

### Compaction (1)
17. `test_archive_dir_under_runtime_groups` — アーカイブパスが runtime/groups/ 下

### Status (2)
18. `test_write_status_under_runtime` — status.json が runtime/ 下に書き込まれる
19. `test_read_status_under_runtime` — status.json が runtime/ 下から読める

### MCP (1)
20. `test_mcp_config_paths_uses_state_root` — MCPパスが state_root 直下を指す

### Skills (4)
21. `test_discover_builtin_skills` — state_root/skills/ 配下のスキルが発見される
22. `test_user_skills_override_builtin` — ユーザースキルが組み込みより優先される
23. `test_discover_both_skill_dirs` — 両ディレクトリがスキャンされる
24. `test_builtin_skills_empty_dir_graceful` — skills/ が存在しなくてもエラーにならない

### Runtime (1)
25. `test_build_app_state_uses_runtime_dir` — build_app_state が runtime_dir 経由で初期化

### 既存テストのリグレッション (2)
26. `test_compaction_creates_archive` — 既存 compaction テストが新パスで動作する
27. `test_full_tool_execution` — ツール実行テストが新パスで動作する

---

## 工数見積もり

| Step | 内容 | 見積もり |
|---|---|---|
| Step 0 | Worktree 作成 | ~5 行 |
| Step 1 | Config 完全リネーム + 派生アクセサ + round-trip | ~200 行 |
| Step 2 | Storage パス変更 | ~40 行 |
| Step 3 | Assets パス変更 | ~40 行 |
| Step 4 | Compaction パス変更 | ~40 行 |
| Step 5 | Status パス変更 | ~40 行 |
| Step 6 | MCP 参照統一 | ~20 行 |
| Step 7 | Skills 組み込みスキャン | ~80 行 |
| Step 8 | 呼び出し側追従 | ~120 行 |
| Step 9 | ドックストリング・コメント掃除 | ~30 行 |
| **合計** | | **~615 行** |
