"""ThreadRepositoryのユニットテスト。

スレッド作成、メッセージ追加、取得操作をテストします。
"""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.infrastructure.database import create_chat_tables
from backend.infrastructure.repositories import AddMessageParams, ThreadRepository


@pytest.fixture
def in_memory_db():
    """インメモリSQLite接続を提供します。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_chat_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def thread_service(in_memory_db):
    """ThreadRepositoryインスタンスを提供します。"""
    return ThreadRepository(in_memory_db)


def test_create_thread(thread_service):
    """スレッド作成をテストします。"""
    user_id = "test_user"
    message = "This is a test message for thread creation"

    thread = thread_service.create_thread(user_id, message)

    # UUIDフォーマット検証
    assert uuid.UUID(thread.thread_id)
    assert thread.user_id == user_id
    assert thread.title == message[:50]
    assert thread.preview == message[:50]
    assert thread.message_count == 0
    assert isinstance(thread.created_at, datetime)
    assert isinstance(thread.last_message_at, datetime)
    assert thread.created_at == thread.last_message_at


def test_create_thread_long_title(thread_service):
    """長いメッセージでスレッド作成時のタイトル切り詰めをテストします。"""
    user_id = "test_user"
    long_message = "A" * 100  # 100文字のメッセージ

    thread = thread_service.create_thread(user_id, long_message)

    # タイトルは50文字に切り詰められる
    assert len(thread.title) == 50
    assert thread.title == long_message[:50]


def test_add_message(thread_service):
    """メッセージ追加とlast_message_at更新をテストします。"""
    user_id = "test_user"
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # スレッド作成時のタイムスタンプをモック
    with patch(
        "backend.infrastructure.repositories.thread_repository.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = base_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        thread = thread_service.create_thread(user_id, "Initial message")
        initial_last_message_at = thread.last_message_at

    # メッセージ追加時は1分後のタイムスタンプをモック
    later_time = base_time + timedelta(minutes=1)
    with patch(
        "backend.infrastructure.repositories.thread_repository.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = later_time
        # datetime.fromisoformat() が元の datetime を使用するように設定
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

        message_content = "Follow-up message"
        message = thread_service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="user",
                content=message_content,
            )
        )

    # メッセージ検証
    assert uuid.UUID(message.message_id)
    assert message.thread_id == thread.thread_id
    assert message.user_id == user_id
    assert message.role == "user"
    assert message.content == message_content
    assert isinstance(message.created_at, datetime)
    assert message.created_at == later_time

    # last_message_at更新確認
    updated_thread = thread_service.get_thread(thread.thread_id)
    assert updated_thread is not None
    assert updated_thread.last_message_at > initial_last_message_at
    assert updated_thread.preview == message_content
    assert updated_thread.message_count == 1


def test_get_threads_pagination(thread_service):
    """スレッド一覧取得とページングをテストします。"""
    user_id = "test_user"
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 複数スレッドを作成（時間順）
    threads = []
    for i in range(5):
        # 各スレッドの作成時刻を1分ずつずらす
        with patch(
            "backend.infrastructure.repositories.thread_repository.datetime"
        ) as mock_datetime:
            current_time = base_time + timedelta(minutes=i)
            mock_datetime.now.return_value = current_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            thread = thread_service.create_thread(user_id, f"Message {i}")
            threads.append(thread)

    # ページング取得
    result_threads, total = thread_service.get_threads(user_id, limit=2, offset=0)

    assert total == 5
    assert len(result_threads) == 2

    # last_message_at降順で返されることを確認（最新が先頭）
    assert result_threads[0].thread_id == threads[-1].thread_id
    assert result_threads[1].thread_id == threads[-2].thread_id

    # 2ページ目を取得
    result_threads_page2, total_page2 = thread_service.get_threads(
        user_id, limit=2, offset=2
    )

    assert total_page2 == 5
    assert len(result_threads_page2) == 2
    assert result_threads_page2[0].thread_id == threads[-3].thread_id


def test_get_threads_empty(thread_service):
    """スレッドが存在しない場合の一覧取得をテストします。"""
    user_id = "nonexistent_user"

    threads, total = thread_service.get_threads(user_id, limit=50, offset=0)

    assert total == 0
    assert len(threads) == 0


def test_get_thread(thread_service):
    """スレッド詳細取得をテストします。"""
    user_id = "test_user"
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch(
        "backend.infrastructure.repositories.thread_repository.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = base_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        thread = thread_service.create_thread(user_id, "Test message")

    # 取得
    retrieved_thread = thread_service.get_thread(thread.thread_id)

    assert retrieved_thread is not None
    assert retrieved_thread.thread_id == thread.thread_id
    assert retrieved_thread.user_id == user_id
    assert retrieved_thread.title == thread.title
    assert retrieved_thread.preview is None
    assert retrieved_thread.message_count == 0


def test_get_thread_not_found(thread_service):
    """存在しないスレッド取得をテストします。"""
    nonexistent_id = str(uuid.uuid4())

    thread = thread_service.get_thread(nonexistent_id)

    assert thread is None


def test_get_messages(thread_service):
    """メッセージ取得と時系列順をテストします。"""
    user_id = "test_user"
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # スレッドとメッセージを作成
    with patch(
        "backend.infrastructure.repositories.thread_repository.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = base_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        thread = thread_service.create_thread(user_id, "First message")

    message_ids = []
    for i in range(3):
        # 各メッセージを1分ずつずらして作成
        with patch(
            "backend.infrastructure.repositories.thread_repository.datetime"
        ) as mock_datetime:
            current_time = base_time + timedelta(minutes=i + 1)
            mock_datetime.now.return_value = current_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            msg = thread_service.add_message(
                AddMessageParams(
                    thread_id=thread.thread_id,
                    user_id=user_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                )
            )
            message_ids.append(msg.message_id)

    # メッセージ取得
    messages = thread_service.get_messages(thread.thread_id)

    # 件数確認（初回メッセージはcreate_thread時に保存されていない想定なので+3）
    assert len(messages) == 3

    # 時系列順（created_at昇順）確認
    for i in range(len(messages)):
        assert messages[i].message_id == message_ids[i]
        assert messages[i].content == f"Message {i}"


def test_get_messages_empty_thread(thread_service):
    """メッセージがないスレッドの取得をテストします。"""
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Initial message")

    # create_threadはメッセージを保存しない（chat.pyで保存される）
    # したがってmessagesテーブルは空のはず
    messages = thread_service.get_messages(thread.thread_id)

    # create_thread後すぐなのでメッセージは0件
    assert len(messages) == 0


def test_timezone_utc(thread_service):
    """タイムゾーンがUTCであることをテストします。"""
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")

    # UTCタイムゾーン確認
    assert thread.created_at.tzinfo == timezone.utc
    assert thread.last_message_at.tzinfo == timezone.utc

    # メッセージ追加
    message = thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="user",
            content="Follow-up",
        )
    )

    assert message.created_at.tzinfo == timezone.utc


def test_add_message_with_model_name(thread_service):
    """model_nameパラメータが正しく保存される。"""
    # Arrange
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")
    model_name = "deepseek/deepseek-v3.2"

    # Act
    message = thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="assistant",
            content="Test response",
            model_name=model_name,
        )
    )

    # Assert
    assert message.model_name == model_name
    assert message.role == "assistant"


def test_add_message_without_model_name(thread_service):
    """model_nameがNoneの場合も保存される。"""
    # Arrange
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")

    # Act
    message = thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="user",
            content="User message",
            model_name=None,
        )
    )

    # Assert
    assert message.model_name is None
    assert message.role == "user"


def test_add_message_model_name_default_value(thread_service):
    """model_nameのデフォルト値がNoneである。"""
    # Arrange
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")

    # Act: model_name引数を省略
    message = thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="user",
            content="User message",
        )
    )

    # Assert
    assert message.model_name is None


def test_get_messages_includes_model_name(thread_service):
    """get_messagesで取得したメッセージにmodel_nameが含まれる。"""
    # Arrange
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")

    # ユーザーメッセージ（model_nameなし）
    thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="user",
            content="User question",
            model_name=None,
        )
    )

    # アシスタントメッセージ（model_nameあり）
    model_name = "gpt-4o-mini"
    thread_service.add_message(
        AddMessageParams(
            thread_id=thread.thread_id,
            user_id=user_id,
            role="assistant",
            content="Assistant response",
            model_name=model_name,
        )
    )

    # Act
    messages = thread_service.get_messages(thread.thread_id)

    # Assert
    assert len(messages) == 2

    # 1番目: ユーザーメッセージ
    assert messages[0].role == "user"
    assert messages[0].model_name is None

    # 2番目: アシスタントメッセージ
    assert messages[1].role == "assistant"
    assert messages[1].model_name == model_name


def test_get_messages_multiple_models(thread_service):
    """複数の異なるモデルを使用したメッセージが正しく保存・取得される。"""
    # Arrange
    user_id = "test_user"
    thread = thread_service.create_thread(user_id, "Test message")

    models = [
        "gpt-4o-mini",
        "deepseek/deepseek-v3.2",
        "x-ai/grok-4.1-fast",
    ]

    # 複数のモデルでアシスタントメッセージを追加
    for i, model in enumerate(models):
        # ユーザーメッセージ
        thread_service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="user",
                content=f"Question {i}",
            )
        )
        # アシスタントメッセージ
        thread_service.add_message(
            AddMessageParams(
                thread_id=thread.thread_id,
                user_id=user_id,
                role="assistant",
                content=f"Response {i}",
                model_name=model,
            )
        )

    # Act
    messages = thread_service.get_messages(thread.thread_id)

    # Assert
    assert len(messages) == 6  # 3ペア（user + assistant）

    # 各アシスタントメッセージが正しいモデル名を持つことを確認
    assistant_messages = [msg for msg in messages if msg.role == "assistant"]
    assert len(assistant_messages) == 3
    for i, msg in enumerate(assistant_messages):
        assert msg.model_name == models[i]
