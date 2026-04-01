"""Chat Domain Models.

チャット会話に関するドメインモデルを定義します。
"""

from dataclasses import dataclass, field

from backend.domain.models.llm import Message


@dataclass
class ConversationContext:
    """会話コンテキスト。

    チャット会話の状態を保持するドメインモデルです。
    ユーザーID、スレッドID、モデル名、メッセージ履歴を管理します。
    """

    user_id: str
    model_name: str
    messages: list[Message] = field(default_factory=list)
    thread_id: str | None = None

    def add_message(self, message: Message) -> None:
        """会話にメッセージを追加します。

        Args:
            message: 追加するメッセージ
        """
        self.messages.append(message)

    def has_system_message(self) -> bool:
        """システムメッセージが含まれているかどうかを判定します。

        Returns:
            bool: システムメッセージが含まれている場合True
        """
        return any(msg.role == "system" for msg in self.messages)

    def get_last_user_message(self) -> Message | None:
        """最後のユーザーメッセージを取得します。

        Returns:
            Message | None: 最後のユーザーメッセージ(存在しない場合はNone)
        """
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

    def get_first_user_message(self) -> Message | None:
        """最初のユーザーメッセージを取得します。

        Returns:
            Message | None: 最初のユーザーメッセージ(存在しない場合はNone)
        """
        for msg in self.messages:
            if msg.role == "user":
                return msg
        return None
