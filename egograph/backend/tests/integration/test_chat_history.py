"""チャット履歴永続化の統合テスト。

/v1/chat エンドポイントでのthread_id処理をテストします。
"""

from backend.infrastructure.llm import client as llm_client_module
from backend.tests.fixtures.llm_responses import mock_chat_response


def test_chat_new_thread(test_client_with_chat_db, monkeypatch):
    """新規スレッド作成フロー（thread_id=None）をテストします。"""

    # LLMレスポンスをモック
    async def mock_chat(*args, **kwargs):
        return mock_chat_response(content="Hello! How can I help you today?")

    async def mock_chat_stream(*args, **kwargs):  # type: ignore
        return  # Empty async generator
        yield

    monkeypatch.setattr(llm_client_module.LLMClient, "chat", mock_chat)
    monkeypatch.setattr(llm_client_module.LLMClient, "chat_stream", mock_chat_stream)

    # リクエスト（thread_idなし）
    response = test_client_with_chat_db.post(
        "/v1/chat",
        json={
            "messages": [{"role": "user", "content": "Hello, this is my first message"}]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # thread_idが返される
    assert "thread_id" in data
    thread_id = data["thread_id"]
    assert len(thread_id) == 36  # UUIDフォーマット

    # スレッド一覧を取得して確認
    threads_response = test_client_with_chat_db.get("/v1/threads")
    assert threads_response.status_code == 200
    threads_data = threads_response.json()

    assert threads_data["total"] == 1
    assert len(threads_data["threads"]) == 1
    assert threads_data["threads"][0]["thread_id"] == thread_id
    assert threads_data["threads"][0]["title"] == "Hello, this is my first message"
    assert threads_data["threads"][0]["preview"] == "Hello! How can I help you today?"
    assert threads_data["threads"][0]["message_count"] == 2


def test_chat_existing_thread(test_client_with_chat_db, monkeypatch):
    """既存スレッドへのメッセージ追加をテストします。"""

    # LLMレスポンスをモック
    async def mock_chat(*args, **kwargs):
        return mock_chat_response(content="I'm doing well, thank you!")

    async def mock_chat_stream(*args, **kwargs):  # type: ignore
        return  # Empty async generator
        yield

    monkeypatch.setattr(llm_client_module.LLMClient, "chat", mock_chat)
    monkeypatch.setattr(llm_client_module.LLMClient, "chat_stream", mock_chat_stream)

    # 新規スレッド作成
    first_response = test_client_with_chat_db.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello, how are you?"}]},
    )
    assert first_response.status_code == 200
    thread_id = first_response.json()["thread_id"]

    # 同じスレッドに追加メッセージ
    second_response = test_client_with_chat_db.post(
        "/v1/chat",
        json={
            "messages": [
                {"role": "user", "content": "Hello, how are you?"},
                {
                    "role": "assistant",
                    "content": "I'm doing well, thank you!",
                },
                {"role": "user", "content": "What's the weather like?"},
            ],
            "thread_id": thread_id,
        },
    )

    assert second_response.status_code == 200
    data = second_response.json()
    assert data["thread_id"] == thread_id

    # メッセージ履歴を取得して確認
    messages_response = test_client_with_chat_db.get(
        f"/v1/threads/{thread_id}/messages"
    )
    assert messages_response.status_code == 200
    messages_data = messages_response.json()

    # ユーザー2回 + アシスタント2回 = 4メッセージ
    assert len(messages_data["messages"]) == 4
    assert messages_data["messages"][0]["role"] == "user"
    assert messages_data["messages"][0]["content"] == "Hello, how are you?"
    assert messages_data["messages"][1]["role"] == "assistant"
    assert messages_data["messages"][2]["role"] == "user"
    assert messages_data["messages"][2]["content"] == "What's the weather like?"
    assert messages_data["messages"][3]["role"] == "assistant"


def test_chat_nonexistent_thread(test_client_with_chat_db, monkeypatch):
    """存在しないthread_idで404エラーをテストします。"""

    # LLMレスポンスをモック（使用されない）
    async def mock_chat(*args, **kwargs):
        return mock_chat_response(content="Should not be called")

    async def mock_chat_stream(*args, **kwargs):  # type: ignore
        return  # Empty async generator
        yield

    monkeypatch.setattr(llm_client_module.LLMClient, "chat", mock_chat)
    monkeypatch.setattr(llm_client_module.LLMClient, "chat_stream", mock_chat_stream)

    # 存在しないthread_id
    nonexistent_thread_id = "00000000-0000-0000-0000-000000000000"

    response = test_client_with_chat_db.post(
        "/v1/chat",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "thread_id": nonexistent_thread_id,
        },
    )

    assert response.status_code == 404
    assert "Thread not found" in response.json()["detail"]


def test_chat_no_user_message(test_client_with_chat_db):
    """ユーザーメッセージがない場合のエラーをテストします。"""
    response = test_client_with_chat_db.post(
        "/v1/chat",
        json={
            "messages": [{"role": "system", "content": "You are a helpful assistant"}]
        },
    )

    assert response.status_code == 400
    assert "At least one user message is required" in response.json()["detail"]


def test_get_thread_not_found(test_client_with_chat_db):
    """存在しないthread_idでスレッド取得時に404エラーをテストします。"""
    nonexistent_thread_id = "00000000-0000-0000-0000-000000000000"

    response = test_client_with_chat_db.get(f"/v1/threads/{nonexistent_thread_id}")

    assert response.status_code == 404
    assert "Thread not found" in response.json()["detail"]


def test_get_thread_messages_not_found(test_client_with_chat_db):
    """存在しないthread_idでメッセージ取得時に404エラーをテストします。"""
    nonexistent_thread_id = "00000000-0000-0000-0000-000000000000"

    response = test_client_with_chat_db.get(
        f"/v1/threads/{nonexistent_thread_id}/messages"
    )

    assert response.status_code == 404
    assert "Thread not found" in response.json()["detail"]


def test_get_thread_invalid_uuid_format(test_client_with_chat_db):
    """不正なUUID形式のthread_idで422エラーをテストします。"""
    invalid_thread_id = "not-a-valid-uuid"

    response = test_client_with_chat_db.get(f"/v1/threads/{invalid_thread_id}")

    # FastAPIのバリデーションエラーまたは404
    # 実装によって異なるため、どちらかであればOK
    assert response.status_code in [404, 422]


def test_chat_with_invalid_thread_id_format(test_client_with_chat_db, monkeypatch):
    """不正な形式のthread_idでチャットリクエストをテストします。"""

    # LLMレスポンスをモック（使用されないが設定は必要）
    async def mock_chat(*args, **kwargs):
        return mock_chat_response(content="Should not be called")

    async def mock_chat_stream(*args, **kwargs):  # type: ignore
        return  # Empty async generator
        yield

    monkeypatch.setattr(llm_client_module.LLMClient, "chat", mock_chat)
    monkeypatch.setattr(llm_client_module.LLMClient, "chat_stream", mock_chat_stream)

    invalid_thread_id = "invalid-uuid-format"

    response = test_client_with_chat_db.post(
        "/v1/chat",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "thread_id": invalid_thread_id,
        },
    )

    # 存在しないthread_idとして扱われ404
    assert response.status_code == 404
    assert "Thread not found" in response.json()["detail"]
