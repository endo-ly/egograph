# Pipelines テスト戦略

Pipelines Service のテスト実装に関する標準ガイドライン。

## 1. テスト層の責務

| 層 | ディレクトリ | 責務 | 外部依存 | CI |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | 単一コンポーネントのロジック正しさ・境界条件を検証。モックで外部依存を遮断。 | なし（全てモック） | ✅ |
| **Integration** | `tests/integration/` | パイプライン全体の契約・連携を検証。モックレスポンスを使い Collector→Transform→Storage の流れを通す。 | モックレスポンス | ✅ |
| **E2E** | `tests/e2e/` | サービス全体のオーケストレーションを検証。API→Dispatcher→Executor→Storage をインメモリS3で通す。 | in-memory S3 | ✅ |
| **Live** | `tests/live/` | 実外部APIとの接続を検証。認証情報が必要。CIからは除外。 | **実API** | ❌ |

### 各層の判断基準

- **Unit**: 「この関数は期待通りの値を返すか？」— 実装の正しさを保証
- **Integration**: 「コンポーネント間のデータ受け渡しは正しいか？」— 契約の正しさを保証
- **E2E**: 「エンドユーザーの操作フローは成立するか？」— システム全体の動作を保証
- **Live**: 「実サービスは現在応答するか？」— 環境・認証・API互換性を保証

## 2. ディレクトリ構成

```
egograph/pipelines/tests/
├── unit/           # 単一コンポーネントのテスト
├── integration/    # パイプライン全体の結合テスト
├── e2e/           # サービス全体のエンドツーエンドテスト
├── live/          # 実APIテスト（CI除外）
├── fixtures/      # 共有フィクスチャ・モックレスポンス
└── conftest.py    # 共有フィクスチャ定義
```

## 3. テスト実行コマンド

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

## 4. 規約

- 全テストメソッドは AAA パターン（Arrange → Act → Assert）で記述
- Docstring は日本語でテストの目的を記述
- ファイル名は `test_{対象}.py`、メソッド名は `test_{条件}_{期待結果}`
