---
title: OpenClaw 外部 Worker オーケストレーション仕様書 v2
aliases:
  - OpenClaw Worker Orchestration Spec v2
  - OpenClaw Orchestration Gateway Spec v2
tags:
  - openclaw
  - gateway
  - orchestration
  - tmux
  - git-worktree
  - sqlite
  - worker
  - control-plane
status: draft
version: 0.2.0
created: 2026-03-25
updated: 2026-03-25
supersedes:
  - docs/00.project/features/openclaw_worker_orchestration_spec.md
---

# OpenClaw 外部 Worker オーケストレーション仕様書 v2

## 1. Summary

本仕様は、OpenClaw を「会話・判断」に特化させ、実際の開発作業を外部 Worker に委譲するための実装可能な v2 設計を定義する。

v2 の主眼は以下である。

- 司令塔と実行基盤を明確に分離する
- Gateway 内に `terminal surface` と `orchestration surface` を分離配置する
- Task ではなく **Task Attempt** を実行の最小単位として扱う
- Worker の二重実行を防ぐため、**claim / lease / heartbeat / reconcile** を導入する
- tmux は観測・介入可能な実行基盤として使い、attempt 単位で隔離する
- git worktree は attempt 単位で分離し、作業衝突を避ける
- 初期構成は単一 Gateway ノード + SQLite で完結させる
- 将来の別 repo / 別 service 化に耐える境界で設計する

---

## 2. Goal / Non-Goal

### 2.1 Goal

- OpenClaw Main / Adviser が実装作業をせずに Worker を指揮できる
- Gateway が Worker 実行の control plane として振る舞える
- Worker が task を安全に claim し、attempt 単位で実行できる
- task 状態、question、artifact、監査情報を durable に追跡できる
- 人間が必要時のみ tmux attach で介入できる
- 将来、orchestration surface だけを別 repo に分離できる

### 2.2 Non-Goal

- 複数 Gateway ノードによる分散協調
- マルチテナント運用
- 大規模ジョブスケジューラ相当の汎用 orchestrator 化
- Worker 内部 CLI の詳細標準化
- AgentMail の本実装
- 本番 CI/CD や secrets manager の最終決定

---

## 3. Design Principles

1. **会話と実行を分離する**
OpenClaw は会話・判断、Gateway は制御、Worker は実行を担う。

2. **Task と Attempt を分離する**
Task は依頼の論理単位、Attempt は実行の物理単位とする。

3. **実行権は lease で管理する**
Worker は task を claim して lease を取得した attempt のみ実行できる。

4. **tmux は身体、SQLite は durable state、Gateway は reconcile 役である**
真実は DB 単体に閉じず、Gateway が外部実態との差分を収束させる。

5. **人間介入は常に可能にする**
自動化を優先するが、途中 attach・確認・再開の経路を必ず残す。

6. **今は同 repo、将来は分離可能にする**
モジュール境界・API 境界・DB 境界は最初から分ける。

---

## 4. System Context

```text
[ User ]
   |
   v
[ OpenClaw ]
  |- Main
  \- Adviser
   |
   v
[ Gateway ]
  |- Terminal Surface
  |   \- human terminal access
  |
  \- Orchestration Surface
      |- Task API
      |- Dispatcher
      |- Worker Registry
      |- Lease Manager
      |- State Manager
      |- Reconciler
      \- SQLite
   |
   v
[ Worker LXC ]
  |- runtime wrapper
  |- git worktree
  |- tmux session
  \- gateway client
```

### 4.1 Terminal Surface

既存の mobile terminal gateway に近い責務を持つ。

- tmux session 一覧
- attach / resize / input / output
- snapshot
- push notification
- 人間向け認証

### 4.2 Orchestration Surface

本仕様の主役。Worker 制御に特化する。

- task 作成
- worker claim / assign
- attempt 生成
- lease / heartbeat
- question / escalation
- artifact / receipt 記録
- reconcile

### 4.3 境界ルール

- Terminal Surface は task scheduling を持たない
- Orchestration Surface は人間向け terminal UX を持たない
- 共通化するのは tmux 操作、ログ基盤、最低限の認証ユーティリティまでとする

---

## 5. Architecture Decision

### 5.1 採用方針

`gateway` リポジトリ内に orchestration surface を追加する。ただし内部構造は独立 service に近い境界で切る。

### 5.2 採用理由

- いま gateway / repo を増やしすぎない
- 既存の tmux / tailscale / notification の知見を活用できる
- 将来の OpenClaw 寄せに向けた足場を作れる

### 5.3 将来の分離条件

以下が複数満たされた場合、orchestration surface の別 repo / 別 service 化を検討する。

- DB スキーマが terminal surface と明確に分離された
- 主な利用者が人間ではなく Worker / OpenClaw になった
- デプロイ頻度や障害影響範囲を分けたい
- mobile terminal 側の変更と独立してリリースしたい
- 共通部分が tmux adapter 程度まで縮退した

---

## 6. Core Domain Model

### 6.1 Task

ユーザーや Main が依頼した論理作業単位。複数回の実行を内包しうる。

例:

- 認証リフレッシュ処理の修正
- Gateway の接続エラー調査

### 6.2 Task Attempt

Worker が実際に task を引き受けて走らせる物理単位。tmux session、worktree、lease は attempt に紐づく。

例:

- 1回目の実行で crash
- 2回目の再試行で別 Worker が再実行

### 6.3 Worker

task を claim して attempt を実行するエージェント実行ノード。

### 6.4 Lease

attempt を実行する権利。一定時間ごとに heartbeat で延長され、失効すると再割当可能になる。

### 6.5 Question

task / attempt 実行中に解決不能となった論点。内部回答とユーザー回答を区別する。

### 6.6 Artifact / Receipt

- Artifact: patch, log summary, test report, build result などの成果物
- Receipt: claim, attach, retry, escalation などの監査記録

---

## 7. Lifecycle

### 7.1 Task Lifecycle

```text
draft -> queued -> in_progress -> completed
                    |             |
                    v             v
                 blocked       failed
                    |
                    v
             awaiting_answer / awaiting_review
```

### 7.2 Attempt Lifecycle

```text
created -> claimed -> preparing -> running -> succeeded
                           |           |          |
                           v           v          v
                        failed      blocked    superseded
                           |
                           v
                       expired
```

### 7.3 重要ルール

- Task は複数 Attempt を持てる
- 同時に `running` になれる Attempt は原則 1つ
- 新 Attempt 作成時、旧 Attempt は `superseded` または `expired` に遷移する
- tmux session と worktree は Attempt に 1対1 で対応する

---

## 8. Claim / Lease / Heartbeat / Reconcile

### 8.1 Claim

Worker は `queued` task を直接実行してはならない。まず Gateway に claim を要求する。

Gateway は以下を原子的に行う。

1. task が claim 可能か確認
2. attempt を作成
3. lease を発行
4. task を `in_progress` に遷移
5. claim receipt を記録

### 8.2 Lease

- lease は短命とし、heartbeat で延長する
- 失効した attempt は実行権を失う
- lease を失った Worker は新規変更を書き込んではならない

### 8.3 Heartbeat

Worker は一定間隔で heartbeat を送る。

Heartbeat に含めるもの:

- attempt_id
- worker_id
- lease_id
- status summary
- current phase
- optional tmux session health

### 8.4 Reconcile

Gateway は定期的に以下を確認し、DB 状態と実態を収束させる。

- heartbeat が途絶えた attempt
- tmux session の存在
- worktree path の存在
- 完了 webhook 未反映
- claim 済みだが preparing から進まない attempt

Reconcile は「DB が絶対」ではなく、「DB を運用上正しい状態に戻す」責務を持つ。

---

## 9. tmux / git worktree Policy

### 9.1 tmux Policy

- tmux session は Attempt 単位で作成する
- 別 task / 別 attempt で tmux session を再利用しない
- 再利用は「同一 attempt の resume」のみ許可する
- session 名は attempt を含む一意名とする

推奨形式:

`wk-<worker>-<attempt_shortid>`

### 9.2 worktree Policy

- worktree は Attempt 単位で作成する
- path は task_id ではなく attempt_id を含める
- attempt が終了しても即削除せず、保守期間を設ける
- cleanup は Gateway ではなく worker runtime か専用 cleaner が担う

推奨形式:

`/srv/worktrees/<repo>/<task_id>/<attempt_id>`

### 9.3 branch Policy

- branch は Task 単位で維持する
- 同一 task の再試行 attempt は原則同一 branch を継続利用する
- 新 attempt は既存 branch を fetch し直したうえで作業を継続する

推奨形式:

`task/<task_id>`

### 9.4 理由

- tmux は実行隔離が重要
- branch は論理成果物の継続性が重要
- worktree は物理隔離が重要

この3者は同じ粒度に揃えない。

---

## 10. State Model

### 10.1 Task Status

- `draft`
- `queued`
- `in_progress`
- `awaiting_internal_answer`
- `awaiting_user_answer`
- `awaiting_human_review`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### 10.2 Attempt Status

- `created`
- `claimed`
- `preparing`
- `running`
- `blocked`
- `succeeded`
- `failed`
- `expired`
- `superseded`
- `cancelled`

### 10.3 状態設計ルール

- Task status はユーザーに見せる要約状態
- Attempt status は運用・実行状態
- Task の `blocked` は、「有効 attempt が進められない」ことを意味する
- Task を `completed` にできるのは、有効 attempt が `succeeded` になった時のみ

---

## 11. Data Model

### 11.1 tasks

```sql
CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  parent_task_id TEXT,
  title TEXT NOT NULL,
  description TEXT,
  requested_by TEXT NOT NULL,
  repo_name TEXT,
  repo_path TEXT,
  branch_name TEXT,
  priority INTEGER NOT NULL DEFAULT 50,
  risk_level TEXT NOT NULL DEFAULT 'normal',
  status TEXT NOT NULL,
  latest_attempt_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 11.2 task_attempts

```sql
CREATE TABLE task_attempts (
  attempt_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  worker_id TEXT,
  lease_id TEXT,
  status TEXT NOT NULL,
  tmux_session TEXT,
  worktree_path TEXT,
  run_branch_name TEXT,
  started_at TEXT,
  finished_at TEXT,
  last_heartbeat_at TEXT,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
```

### 11.3 workers

```sql
CREATE TABLE workers (
  worker_id TEXT PRIMARY KEY,
  worker_type TEXT NOT NULL,
  host_name TEXT NOT NULL,
  lxc_name TEXT NOT NULL,
  status TEXT NOT NULL,
  capabilities_json TEXT,
  current_attempt_id TEXT,
  last_heartbeat_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 11.4 leases

```sql
CREATE TABLE leases (
  lease_id TEXT PRIMARY KEY,
  attempt_id TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(attempt_id) REFERENCES task_attempts(attempt_id)
);
```

### 11.5 task_events

```sql
CREATE TABLE task_events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  attempt_id TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
```

### 11.6 questions

```sql
CREATE TABLE questions (
  question_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  attempt_id TEXT,
  target TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  body TEXT NOT NULL,
  answer TEXT,
  asked_by TEXT NOT NULL,
  answered_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
```

### 11.7 artifacts / receipts

artifact と receipt は v1 案を踏襲するが、attempt_id を追加して物理実行と結びつける。

---

## 12. API Design

### 12.1 OpenClaw / Main 向け

- `POST /api/orchestration/tasks`
- `GET /api/orchestration/tasks/{task_id}`
- `GET /api/orchestration/tasks/{task_id}/events`
- `POST /api/orchestration/questions/{question_id}/answer`

### 12.2 Worker 向け

- `POST /api/orchestration/workers/register`
- `POST /api/orchestration/workers/{worker_id}/claim-next`
- `POST /api/orchestration/attempts/{attempt_id}/heartbeat`
- `POST /api/orchestration/attempts/{attempt_id}/events`
- `POST /api/orchestration/attempts/{attempt_id}/complete`
- `POST /api/orchestration/attempts/{attempt_id}/fail`
- `POST /api/orchestration/attempts/{attempt_id}/question`

### 12.3 Human Ops 向け

- `POST /api/orchestration/tasks/{task_id}/cancel`
- `POST /api/orchestration/attempts/{attempt_id}/force-expire`
- `POST /api/orchestration/attempts/{attempt_id}/reconcile`

### 12.4 設計ルール

- state mutation API は idempotency key を受け取る
- event は client-generated `event_id` を必須とする
- attempt に紐づく更新は `attempt_id + lease_id` で認証・検証する
- Worker は task status を直接書き換えず、attempt API を通じて反映する

---

## 13. Question / Approval Policy

### 13.1 原則

通常の inner loop は自動で進める。ただし外部影響は厳密に分離する。

### 13.2 自動で進めてよいもの

- ローカルファイル編集
- lint / format / unit test
- ローカル build
- static analysis
- docs 変更
- patch / report / artifact 生成

### 13.3 自動で進めてはいけないもの

- 外部ネットワーク送信を伴う操作
- 共有環境への書き込み
- package publish
- public push / PR 作成
- 本番 DB 変更
- secrets 参照 / 更新
- destructive migration
- 課金発生操作

### 13.4 質問優先順位

1. Worker 自力解決
2. Main / Adviser に内部質問
3. それでも解けない場合のみユーザー質問

### 13.5 Human Review 条件

- 外部へ出る変更
- security-sensitive な変更
- 不可逆操作
- user-specific な判断が必要な場合

---

## 14. Failure Handling

### 14.1 Worker Crash

- heartbeat timeout で lease 失効
- attempt を `blocked` または `expired` に遷移
- reconcile が tmux / worktree の残骸を確認
- 必要なら新 attempt を作成

### 14.2 Duplicate Execution

- lease により防ぐ
- 二重 claim を検知した場合、後発 attempt を `superseded` にする
- receipt と event に必ず記録する

### 14.3 tmux 残存

- tmux session が残っても lease が切れていれば再開不可
- 同一 attempt resume は明示オペレーションでのみ許可する

### 14.4 Webhook 遅延 / 重複

- idempotency key で吸収する
- completion より古い blocked event は破棄する

### 14.5 Reconcile Failure

- reconcile 自体の結果を receipt に残す
- 自動修復不能なら `awaiting_human_review` に昇格する

---

## 15. Security Model

### 15.1 認証境界

- Terminal Surface: 人間クライアント認証
- Orchestration Surface: Worker / OpenClaw 用の machine auth

同じ gateway 配下でも認証方式と権限境界は分離する。

### 15.2 最小権限

- Worker は自分の claim した attempt のみ更新可能
- Main は task / question 参照と回答は可能、tmux attach は不要
- 人間 Ops は force 操作を持つ

### 15.3 Tailscale の役割

- 通常バスではなく保守経路
- 人間の attach / SSH / 障害調査に用いる

---

## 16. Technology Selection

### 16.1 採用

- **Gateway framework**: 既存 `gateway` を拡張
- **Runtime session**: tmux
- **Workspace isolation**: git worktree
- **Durable state**: SQLite
- **Transport**: HTTP + WebSocket + webhook

### 16.2 採用理由

- tmux: 観測・再接続・人間介入に強い
- git worktree: 並列 task の物理分離に強い
- SQLite: 単一ノード control plane として十分軽量
- HTTP / WebSocket / webhook: 現行資産と相性が良い

### 16.3 不採用

- Postgres: v2 では早い
- Redis を primary state store とする案: 監査性が弱い
- Kubernetes Job / Temporal などの重量 orchestrator: 要件に対して過剰
- 自前 PTY supervision: tmux より実装負荷が高い

### 16.4 将来の移行条件

- 複数 Gateway ノード運用が必要になった
- SQLite の lock / throughput が支配的制約になった
- lease 管理の一貫性要件が上がった

この場合は Postgres 移行を第一候補とする。

---

## 17. Phase Plan

### Phase 1

最小 orchestration surface を作る。

- task / attempt / worker / lease schema
- worker register / claim / heartbeat / complete API
- tmux / worktree attempt 単位運用
- reconcile 最小版

### Phase 2

OpenClaw Main / Adviser 連携を強化する。

- question flow
- internal answer / user escalation
- result summarization

### Phase 3

運用機能を整える。

- human ops API
- artifact preview
- richer receipts
- cleaner / retention

### Phase 4

必要に応じて別 repo / 別 service 化を検討する。

---

## 18. Acceptance Criteria

- Main が task を作成できる
- Worker が task を claim し、attempt / lease を取得できる
- 同一 task の二重実行が防止される
- attempt ごとに tmux session と worktree が分離される
- heartbeat timeout により stale attempt を失効できる
- reconcile により不整合を検知できる
- question が internal / user / human review に正しく振り分けられる
- human が必要時のみ tmux attach で介入できる

---

## 19. Open Questions

- secrets 配布方式
- Worker capability routing の詳細
- branch を task 単位に固定するか、attempt ごとに派生させるか
- artifact retention 期間
- AgentMail mirror の詳細粒度
- OpenClaw Main / Adviser の prompt / skill 設計

---

## 20. One-Sentence Summary

**Gateway 内に orchestration surface を新設し、Task と Attempt を分離した lease ベース制御で Worker を運用する。tmux は attempt 単位の実行基盤、git worktree は attempt 単位の作業分離、SQLite は単一ノード control plane の durable state として用い、将来の別 repo 分離に耐える境界で設計する。**
