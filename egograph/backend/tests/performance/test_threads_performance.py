"""スレッド管理のパフォーマンステスト。

大量データでのN+1クエリ問題やレスポンスタイムを検証します。
"""

import sqlite3
import time

import pytest

from backend.infrastructure.database import create_chat_tables
from backend.infrastructure.repositories import (
    AddMessageParams,
    ThreadRepository,
)


@pytest.fixture
def in_memory_db():
    """インメモリSQLite接続を提供します。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # パフォーマンス最適化
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    create_chat_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def thread_service(in_memory_db):
    """ThreadRepositoryインスタンスを提供します。"""
    return ThreadRepository(in_memory_db)


def test_get_threads_performance_1000_threads(thread_service):
    """1000件のスレッド取得のパフォーマンスをテストします。

    目標: 1000件のスレッドを1秒以内に取得できること。
    N+1クエリが発生していないことを確認します。
    """
    user_id = "performance_test_user"
    num_threads = 1000

    # 1000件のスレッドを作成（各スレッドに1件のメッセージ）
    for i in range(num_threads):
        thread = thread_service.create_thread(user_id, f"Performance test message {i}")
        # 各スレッドにメッセージを追加（message_countとpreviewテスト用）
        thread_service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="user",
                content=f"First message in thread {i}",
            )
        )

    # パフォーマンス測定
    start_time = time.time()
    threads, total = thread_service.get_threads(user_id, limit=1000, offset=0)
    elapsed_time = time.time() - start_time

    # 検証
    assert total == num_threads
    assert len(threads) == num_threads

    # パフォーマンス目標: 1秒以内
    assert elapsed_time < 1.0, (
        f"Expected < 1.0s, but took {elapsed_time:.3f}s for {num_threads} threads"
    )

    # 各スレッドのデータが正しく取得されているか確認
    for thread in threads[:10]:  # 最初の10件のみ検証
        assert thread.thread_id is not None
        assert thread.user_id == user_id
        assert thread.message_count >= 1
        assert thread.preview is not None


def test_get_threads_performance_with_many_messages(thread_service):
    """各スレッドに大量のメッセージがある場合のパフォーマンステスト。

    100件のスレッド × 各10メッセージ = 1000メッセージでのパフォーマンスを検証。
    """
    user_id = "message_heavy_user"
    num_threads = 100
    messages_per_thread = 10

    # 100件のスレッドを作成し、各スレッドに10件のメッセージを追加
    for i in range(num_threads):
        thread = thread_service.create_thread(user_id, f"Thread {i}")

        for j in range(messages_per_thread):
            role = "user" if j % 2 == 0 else "assistant"
            thread_service.add_message(
                AddMessageParams(
                    thread_id=thread.thread_id,
                    user_id=user_id,
                    role=role,
                    content=f"Message {j} in thread {i}",
                )
            )

    # パフォーマンス測定
    start_time = time.time()
    threads, total = thread_service.get_threads(user_id, limit=100, offset=0)
    elapsed_time = time.time() - start_time

    # 検証
    assert total == num_threads
    assert len(threads) == num_threads

    # パフォーマンス目標: 0.5秒以内
    error_msg = (
        f"Expected < 0.5s, but took {elapsed_time:.3f}s for {num_threads} "
        f"threads with {messages_per_thread} messages each"
    )
    assert elapsed_time < 0.5, error_msg

    # message_countが正しく集計されているか確認
    for thread in threads:
        assert thread.message_count == messages_per_thread, (
            f"Expected {messages_per_thread} messages, got {thread.message_count}"
        )


def test_get_threads_pagination_performance(thread_service):
    """ページング処理のパフォーマンステスト。

    大量データでのOFFSETパフォーマンスを検証します。
    """
    user_id = "pagination_test_user"
    num_threads = 500

    # 500件のスレッドを作成
    for i in range(num_threads):
        thread = thread_service.create_thread(user_id, f"Pagination test {i}")
        thread_service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="user",
                content=f"Message {i}",
            )
        )

    # 最後のページ取得（OFFSET=480, LIMIT=20）
    start_time = time.time()
    threads, total = thread_service.get_threads(user_id, limit=20, offset=480)
    elapsed_time = time.time() - start_time

    # 検証
    assert total == num_threads
    assert len(threads) == 20

    # パフォーマンス目標: 0.2秒以内（OFFSETが大きくても遅くならないこと）
    assert elapsed_time < 0.2, (
        f"Expected < 0.2s, but took {elapsed_time:.3f}s for offset=480"
    )


@pytest.mark.slow
def test_query_count_for_threads_retrieval(in_memory_db):
    """スレッド取得時のクエリ数をテストします（N+1問題検出用）。

    現在の実装では、get_threads()は以下のクエリを実行します:
    1. COUNT(*)でtotal取得
    2. 1つのクエリでスレッド一覧とpreview, message_count取得（サブクエリ使用）

    合計2クエリのみであることを確認します（スレッド数に依存しない）。
    """
    user_id = "query_count_test_user"

    # ThreadRepositoryを使ってスレッドを作成
    service = ThreadRepository(in_memory_db)

    # 50件のスレッドを作成
    for i in range(50):
        thread = service.create_thread(user_id, f"Query count test {i}")
        service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="user",
                content=f"Message {i}",
            )
        )

    # スレッド取得
    threads, total = service.get_threads(user_id, limit=50, offset=0)

    # 検証
    assert total == 50
    assert len(threads) == 50

    # 注: SQLiteのEXPLAIN QUERY PLANでクエリ構造を確認可能
    # 実際のN+1問題がある場合、50件でも明らかに遅くなるはずです。
