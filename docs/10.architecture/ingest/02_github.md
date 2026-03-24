# GitHub データソース

## 1. 概要

- **データの性質**: 構造化ログ
- **粒度**: Atomic (イベント単位)
- **更新頻度**: 日次
- **センシティビティレベル**: Medium (公開リポジトリは Low)

---

## 2. 対象データ

| データタイプ | 説明 | 取得方法 |
|-------------|------|----------|
| commits | コミット履歴 | GitHub API (`GET /repos/{owner}/{repo}/commits`) |
| issues | Issue 作成・更新 | GitHub API (`GET /repos/{owner}/{repo}/issues`) |
| pull_requests | PR 作成・更新 | GitHub API (`GET /repos/{owner}/{repo}/pulls`) |
| reviews | PR レビュー | GitHub API (`GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews`) |
| workflow_runs | GitHub Actions 実行履歴 | GitHub API (`GET /repos/{owner}/{repo}/actions/runs`) |

---

## 3. スキーマ定義

### 3.1 共通フィールド

| フィールド | 型 | 説明 |
|-----------|---|------|
| `id` | string | 一意識別子 (GitHub API の ID) |
| `timestamp` | datetime | イベント発生時刻 (UTC) |
| `event_type` | string | イベントタイプ (commit, issue, pr, review, workflow_run) |
| `repository` | string | リポジトリ名 (owner/repo 形式) |
| `actor` | string | 実行者の GitHub ユーザー名 |
| `payload` | json | イベント固有のデータ |

### 3.2 Parquet 保存先

```
s3://ego-graph/events/github/
  ├── year=2024/
  │   ├── month=01/
  │   │   └── data.parquet
  │   └── month=02/
  │       └── data.parquet
  └── ...
```

---

## 4. ワークフロー

- **ワークフロー**: `job-ingest-github.yml`
- **実行タイミング**: Cron (1日2回: 00:00 UTC, 12:00 UTC)
- **増分取り込み**: R2 内のカーソル (state/github_cursor.json) で管理

---

## 5. 実装詳細

### 5.1 ディレクトリ構成

```
ingest/github/
├── __init__.py
├── main.py           # エントリーポイント
├── collector.py      # GitHub API データ取得
├── transform.py      # データ変換・正規化
├── storage.py        # R2 アップロード
├── pipeline.py       # ETL パイプライン統合
└── compact.py        # Parquet 最適化
```

### 5.2 認証

- **認証方式**: GitHub Personal Access Token (PAT)
- **必要なスコープ**: `repo`, `read:user`
- **環境変数**: `GITHUB_TOKEN`

---

## 6. Semantification 戦略

### 6.1 自然言語化テンプレート

| イベントタイプ | テンプレート |
|--------------|-------------|
| commit | `{repository}で{message}をコミットした` |
| issue_open | `{repository}でIssue #{number}: {title}を作成した` |
| issue_close | `{repository}でIssue #{number}: {title}をクローズした` |
| pr_open | `{repository}でPR #{number}: {title}を作成した` |
| pr_merge | `{repository}でPR #{number}: {title}をマージした` |
| review | `{repository}のPR #{pr_number}をレビューした` |
| workflow_success | `{repository}でワークフロー{workflow_name}が成功した` |
| workflow_failure | `{repository}でワークフロー{workflow_name}が失敗した` |

---

## 7. 検索シナリオ例

| 質問 | 検索戦略 |
|-----|---------|
| 「先週どんなコードを書いた？」 | `event_type=commit`, `timestamp` で期間フィルタ |
| 「最近マージしたPRは？」 | `event_type=pr_merge`, `timestamp` で降順ソート |
| 「失敗したワークフローは？」 | `event_type=workflow_failure` |

---

## 8. 参考

- [GitHub REST API Documentation](https://docs.github.com/rest)
- [Ingest 共通アーキテクチャ](./README.md)
- [データモデル](../1002_data_model.md)
