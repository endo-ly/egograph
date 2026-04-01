"""チャット履歴用のAPIスキーマ。

スレッドとメッセージのAPIレスポンス構造を定義します。
"""

from pydantic import BaseModel

from backend.domain.models.thread import Thread, ThreadMessage


class ThreadListResponse(BaseModel):
    """スレッド一覧のレスポンス。

    Attributes:
        threads: スレッドのリスト（last_message_at降順）
        total: 総スレッド数
        limit: 1ページあたりの件数
        offset: オフセット
    """

    threads: list[Thread]
    total: int
    limit: int
    offset: int


class ThreadMessagesResponse(BaseModel):
    """スレッドメッセージのレスポンス。

    Attributes:
        thread_id: スレッドのUUID
        messages: メッセージのリスト（created_at昇順）
    """

    thread_id: str
    messages: list[ThreadMessage]
