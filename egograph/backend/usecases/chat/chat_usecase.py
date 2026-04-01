"""チャットユースケースの実装。

LLMとの会話全体をオーケストレーションし、スレッド管理からツール実行までを統合します。
"""

import asyncio
import logging
from typing import AsyncGenerator, cast

from pydantic import BaseModel

from backend.config import LLMConfig, R2Config
from backend.domain.models.llm import StreamChunk
from backend.infrastructure.llm import LLMClient, Message
from backend.infrastructure.repositories import (
    AddMessageParams,
    ThreadRepository,
)
from backend.usecases.chat.system_prompt_builder import SystemPromptBuilder
from backend.usecases.chat.tool_executor import (
    MaxIterationsExceeded,
    ToolExecutor,
)
from backend.usecases.tools import ToolRegistry, build_tool_registry

logger = logging.getLogger(__name__)

# スレッド作成の競合状態を防ぐためのロック
_thread_creation_lock = asyncio.Lock()


class ChatUseCaseError(Exception):
    """チャットユースケースエラーの基底クラス。"""

    pass


class NoUserMessageError(ChatUseCaseError):
    """ユーザーメッセージがない場合の例外（→ 400）。"""

    pass


class ThreadNotFoundError(ChatUseCaseError):
    """スレッドが見つからない場合の例外（→ 404）。"""

    pass


class ChatUseCaseRequest(BaseModel):
    """内部用チャットリクエスト。

    API層から受け取ったリクエストを内部処理用に変換したもの。
    """

    messages: list[Message]
    thread_id: str | None
    model_name: str | None
    user_id: str


class ChatResult(BaseModel):
    """チャットユースケースの実行結果。"""

    response_id: str
    message: Message
    thread_id: str
    model_name: str
    usage: dict | None = None


class ChatUseCase:
    """チャット会話全体をオーケストレーションするユースケース。

    スレッド管理、モデル選択、システムプロンプト構築、ツール実行、
    応答の永続化を統合して管理します。
    """

    def __init__(
        self,
        thread_repository: ThreadRepository,
        llm_config: LLMConfig,
        r2_config: R2Config | None,
    ):
        """ChatUseCaseを初期化します。

        Args:
            thread_repository: スレッドリポジトリ
            llm_config: LLM設定
            r2_config: R2ストレージ設定（ツール用）
        """
        self.thread_repository = thread_repository
        self.llm_config = llm_config
        self.r2_config = r2_config

    async def execute(self, request: ChatUseCaseRequest) -> ChatResult:
        """チャット会話を実行します。

        処理フロー:
        1. スレッド管理（新規作成 or 既存取得）
        2. モデル名解決
        3. 会話準備（SystemPromptBuilder使用）
        4. LLM初期化
        5. ツールレジストリ構築
        6. ToolExecutor.execute_loop() 実行
        7. アシスタント応答の永続化

        Args:
            request: チャットリクエスト

        Returns:
            ChatResult: 実行結果

        Raises:
            NoUserMessageError: 新規スレッド作成時にユーザーメッセージがない
            ThreadNotFoundError: 既存スレッドが見つからない
            MaxIterationsExceeded: 最大イテレーション数到達
            asyncio.TimeoutError: タイムアウト発生
        """
        # 1. スレッド管理
        thread_id = await self._handle_thread(request)
        logger.info("Using thread_id=%s for user_id=%s", thread_id, request.user_id)

        # 2. モデル名解決
        used_model_name = (
            request.model_name
            if request.model_name is not None
            else self.llm_config.default_model
        )
        logger.info("Using model_name=%s", used_model_name)

        # 3. 会話準備（システムメッセージ追加）
        conversation_history = self._prepare_conversation(request.messages)

        # 4. LLM初期化
        llm_client = LLMClient.from_config(
            self.llm_config,
            used_model_name,
        )

        # 5. ツールレジストリ構築
        tool_registry = self._build_tool_registry()
        tools = tool_registry.get_all_schemas()

        # 6. ToolExecutor.execute_loop() 実行
        tool_executor = ToolExecutor(
            llm_client=llm_client,
            tool_registry=tool_registry,
            max_iterations=5,
        )

        try:
            result = await tool_executor.execute_loop(
                conversation_history=conversation_history,
                tools=tools,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                timeout=90.0,
            )
        except (MaxIterationsExceeded, asyncio.TimeoutError):
            # これらのエラーは呼び出し側で処理されるべき
            raise

        # 7. アシスタント応答の永続化
        assistant_content = cast(str, result.final_message.content or "")
        self.thread_repository.add_message(
            AddMessageParams(
                thread_id=thread_id,
                user_id=request.user_id,
                role="assistant",
                content=assistant_content,
                model_name=used_model_name,
            )
        )
        logger.info(
            "Saved assistant message to thread_id=%s after %s iterations",
            thread_id,
            result.iterations,
        )

        return ChatResult(
            response_id=result.response_id,
            message=result.final_message,
            thread_id=thread_id,
            model_name=used_model_name,
            usage=result.usage,
        )

    async def _handle_thread(self, request: ChatUseCaseRequest) -> str:
        """スレッド新規作成または既存取得を処理します。

        新規の場合は初回ユーザーメッセージでスレッドを作成し、
        既存の場合はスレッドの存在確認を行います。
        ユーザーメッセージはDBに保存されます。

        Args:
            request: チャットリクエスト

        Returns:
            str: スレッドID

        Raises:
            NoUserMessageError: 新規スレッド作成時にユーザーメッセージがない
            ThreadNotFoundError: 既存スレッドが見つからない
        """
        if request.thread_id is None:
            # 新規スレッド: 初回ユーザーメッセージから作成
            first_user_message = next(
                (msg for msg in request.messages if msg.role == "user"), None
            )
            if first_user_message is None:
                raise NoUserMessageError(
                    "At least one user message is required for new thread"
                )

            # 複数リクエストが同時に到達した場合の重複スレッド作成を防ぐ
            async with _thread_creation_lock:
                # user メッセージの content は常に str
                content = cast(str, first_user_message.content or "")
                thread = self.thread_repository.create_thread(request.user_id, content)
                thread_id = thread.thread_id
                logger.info("Created new thread: thread_id=%s", thread_id)

            # 最新のユーザーメッセージを保存（既存スレッドと同じロジック）
            last_user_message = next(
                (msg for msg in reversed(request.messages) if msg.role == "user"), None
            )
            if last_user_message:
                content = cast(str, last_user_message.content or "")
                self.thread_repository.add_message(
                    AddMessageParams(
                        thread_id=thread_id,
                        user_id=request.user_id,
                        role="user",
                        content=content,
                        model_name=None,  # ユーザーメッセージにはmodel_nameなし
                    )
                )
            return thread_id
        else:
            # 既存スレッド: 存在確認
            thread = self.thread_repository.get_thread(request.thread_id)
            if thread is None:
                raise ThreadNotFoundError(f"Thread not found: {request.thread_id}")

            thread_id = request.thread_id
            logger.info("Using existing thread: thread_id=%s", thread_id)

            # 最新のユーザーメッセージを保存
            last_user_message = next(
                (msg for msg in reversed(request.messages) if msg.role == "user"), None
            )
            if last_user_message:
                content = cast(str, last_user_message.content or "")
                self.thread_repository.add_message(
                    AddMessageParams(
                        thread_id=thread_id,
                        user_id=request.user_id,
                        role="user",
                        content=content,
                        model_name=None,  # ユーザーメッセージにはmodel_nameなし
                    )
                )
            return thread_id

    def _prepare_conversation(self, messages: list[Message]) -> list[Message]:
        """会話履歴を準備し、必要に応じてシステムメッセージを追加します。

        システムメッセージがまだ含まれていない場合、現在日時を含む
        システムプロンプトを先頭に追加します。

        Args:
            messages: 元のメッセージリスト

        Returns:
            list[Message]: システムメッセージを含む会話履歴
        """
        conversation_history = messages.copy()

        # システムメッセージに現在日を追加（まだ含まれていない場合）
        if not any(msg.role == "system" for msg in conversation_history):
            system_message = SystemPromptBuilder.build_with_current_date()
            conversation_history.insert(0, system_message)
            logger.debug("Added system message with current date context")

        return conversation_history

    def _build_tool_registry(self) -> ToolRegistry:
        """ツールレジストリを構築します。

        R2設定が存在する場合、Spotifyツール群とYouTubeツール群を登録します。

        Returns:
            ToolRegistry: 構築されたツールレジストリ
        """
        tool_registry = build_tool_registry(self.r2_config)
        if self.r2_config:
            logger.debug("Registered Spotify + YouTube tools")
        return tool_registry

    async def execute_stream(
        self, request: ChatUseCaseRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """チャット会話をストリーミングで実行します。

        ストリーミングモードでは、最終的な応答のみをストリーミングで返します。
        ツール呼び出しはバックグラウンドで実行されます。

        処理フロー:
        1. スレッド管理（新規作成 or 既存取得）
        2. モデル名解決
        3. 会話準備（SystemPromptBuilder使用）
        4. LLM初期化
        5. ツールレジストリ構築
        6. ToolExecutor.execute_loop_stream() 実行
        7. アシスタント応答の永続化（完了時のみ）

        Args:
            request: チャットリクエスト

        Yields:
            StreamChunk: 各ストリーミングチャンク

        Raises:
            NoUserMessageError: 新規スレッド作成時にユーザーメッセージがない
            ThreadNotFoundError: 既存スレッドが見つからない
            MaxIterationsExceeded: 最大イテレーション数到達
            asyncio.TimeoutError: タイムアウト発生
        """
        # 1. スレッド管理
        thread_id = await self._handle_thread(request)
        logger.info("Using thread_id=%s for user_id=%s", thread_id, request.user_id)

        # 2. モデル名解決
        used_model_name = (
            request.model_name
            if request.model_name is not None
            else self.llm_config.default_model
        )
        logger.info("Using model_name=%s", used_model_name)

        # 3. 会話準備（システムメッセージ追加）
        conversation_history = self._prepare_conversation(request.messages)

        # 4. LLM初期化
        llm_client = LLMClient.from_config(
            self.llm_config,
            used_model_name,
        )

        # 5. ツールレジストリ構築
        tool_registry = self._build_tool_registry()
        tools = tool_registry.get_all_schemas()

        # 6. ToolExecutor.execute_loop_stream() 実行
        tool_executor = ToolExecutor(
            llm_client=llm_client,
            tool_registry=tool_registry,
            max_iterations=5,
        )

        # 最終的な応答を蓄積
        final_content = ""

        try:
            async for chunk in tool_executor.execute_loop_stream(
                conversation_history=conversation_history,
                tools=tools,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                timeout=90.0,
            ):
                if chunk.type == "delta" and chunk.delta:
                    final_content += chunk.delta
                    yield chunk
                elif chunk.type == "done":
                    # doneチャンクにthread_idを追加
                    yield chunk.model_copy(update={"thread_id": thread_id})
                elif chunk.type in ("tool_call", "tool_result", "error"):
                    # ツール呼び出し/結果/エラーもパススルー
                    yield chunk
        except (MaxIterationsExceeded, asyncio.TimeoutError):
            # これらのエラーは呼び出し側で処理されるべき
            raise

        # 7. アシスタント応答の永続化（完了時のみ）
        if final_content:
            self.thread_repository.add_message(
                AddMessageParams(
                    thread_id=thread_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=final_content,
                    model_name=used_model_name,
                )
            )
            logger.info(
                "Saved assistant message to thread_id=%s (length=%s)",
                thread_id,
                len(final_content),
            )
