"""Anthropic (Claude) プロバイダー。"""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from backend.domain.models.llm import ChatResponse, Message, StreamChunk, ToolCall
from backend.domain.models.tool import Tool
from backend.infrastructure.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Messages APIプロバイダー。"""

    def __init__(self, api_key: str, model_name: str):
        """AnthropicProviderを初期化します。

        Args:
            api_key: Anthropic API認証キー
            model_name: モデル名（例: "claude-3-5-sonnet-20241022"）
        """
        super().__init__(api_key, model_name)
        self.base_url = "https://api.anthropic.com/v1"
        self.api_version = "2023-06-01"

    def _convert_message_to_anthropic(self, msg: Message) -> dict:
        """通常メッセージをAnthropic形式に変換します。

        Args:
            msg: 変換するメッセージ

        Returns:
            Anthropic形式のメッセージ
        """
        # assistantメッセージでtool_callsがある場合は、contentとtool_useブロックに変換
        if msg.role == "assistant" and msg.tool_calls:
            content_blocks: list[dict] = []

            # テキストコンテンツがあれば追加
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})

            # tool_callsをtool_useブロックに変換
            for tc in msg.tool_calls:
                # ToolCallオブジェクトから値を取得
                tc_id = tc.id
                tc_name = tc.name
                if not tc_id or not tc_name:
                    raise ValueError(f"Tool call missing id or name: {tc}")
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc_id,
                        "name": tc_name,
                        "input": tc.parameters,
                    }
                )

            return {"role": msg.role, "content": content_blocks}

        # 通常のメッセージはそのまま
        return {"role": msg.role, "content": msg.content}

    def _convert_tool_result_to_anthropic(self, msg: Message) -> dict:
        """ツール結果メッセージをAnthropic形式に変換します。

        Args:
            msg: ツール結果メッセージ（role="tool"）

        Returns:
            Anthropic形式のメッセージ（role="user" with tool_result blocks）

        Raises:
            ValueError: tool_call_idが設定されていない場合
        """
        if not msg.tool_call_id:
            raise ValueError(
                "invalid_tool_result: tool_call_id is required for role='tool' messages"
            )

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else "",
                }
            ],
        }

    async def chat_completion(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """Anthropic Messages APIを呼び出します。

        Args:
            messages: チャットメッセージ履歴
            tools: 利用可能なツール
            temperature: 生成の多様性
            max_tokens: 最大トークン数

        Returns:
            ChatResponse

        Raises:
            httpx.HTTPError: API呼び出しに失敗した場合
        """
        # systemメッセージを分離（複数ある場合は結合）
        system_messages: list[str] = []
        user_messages = []
        for msg in messages:
            if msg.role == "system":
                # systemメッセージのcontentは文字列のみを想定
                if isinstance(msg.content, str):
                    system_messages.append(msg.content)
                elif msg.content is not None:
                    # list形式の場合は警告してスキップ
                    logger.warning(
                        "System message with list content not supported, skipping"
                    )
            elif msg.role == "tool":
                # ツール結果メッセージを変換
                user_messages.append(self._convert_tool_result_to_anthropic(msg))
            else:
                # 通常メッセージを変換
                user_messages.append(self._convert_message_to_anthropic(msg))

        # 複数のsystemメッセージがある場合は改行で結合
        system_message = "\n\n".join(system_messages) if system_messages else None

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            payload["system"] = system_message

        if tools:
            payload["tools"] = self._convert_tools_to_provider_format(tools)

        logger.debug("Sending request to %s/messages", self.base_url)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

            return self._parse_response(response.json())

    def _convert_tools_to_provider_format(self, tools: list[Tool]) -> list[dict]:
        """MCPツールをAnthropic tool_use形式に変換します。

        Args:
            tools: MCPツールリスト

        Returns:
            Anthropic形式のツール定義
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in tools
        ]

    def _parse_response(self, raw: dict) -> ChatResponse:
        """Anthropicレスポンスを統一形式にパースします。

        Args:
            raw: Anthropic APIのレスポンスJSON

        Returns:
            ChatResponse
        """
        # Anthropicのレスポンスは content がリスト形式
        content_blocks = raw["content"]

        # テキストコンテンツを抽出
        text_content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")

        # ツール呼び出しを抽出
        tool_calls = None
        tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
        if tool_use_blocks:
            tool_calls = [
                ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    parameters=block.get("input", {}),
                )
                for block in tool_use_blocks
            ]

        # Usage情報の変換
        usage = None
        if "usage" in raw:
            usage_data = raw.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0)
                + usage_data.get("output_tokens", 0),
            }

        return ChatResponse(
            id=raw.get("id", ""),
            message=Message(
                role="assistant",
                content=text_content or None,
                tool_calls=tool_calls,
            ),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=raw.get("stop_reason", "unknown"),
        )

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Anthropic Messages APIをストリーミングで呼び出します。

        Args:
            messages: チャットメッセージ履歴
            tools: 利用可能なツール
            temperature: 生成の多様性
            max_tokens: 最大トークン数

        Yields:
            StreamChunk: 各ストリーミングチャンク

        Raises:
            httpx.HTTPError: API呼び出しに失敗した場合
        """
        # systemメッセージを分離（複数ある場合は結合）
        system_messages: list[str] = []
        user_messages = []
        for msg in messages:
            if msg.role == "system":
                if isinstance(msg.content, str):
                    system_messages.append(msg.content)
                elif msg.content is not None:
                    logger.warning(
                        "System message with list content not supported, skipping"
                    )
            elif msg.role == "tool":
                # ツール結果メッセージを変換
                user_messages.append(self._convert_tool_result_to_anthropic(msg))
            else:
                # 通常メッセージを変換
                user_messages.append(self._convert_message_to_anthropic(msg))

        # 複数のsystemメッセージがある場合は改行で結合
        system_message = "\n\n".join(system_messages) if system_messages else None

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,  # ストリーミング有効化
        }

        if system_message:
            payload["system"] = system_message

        if tools:
            payload["tools"] = self._convert_tools_to_provider_format(tools)

        logger.debug("Sending streaming request to %s/messages", self.base_url)

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()

                # Anthropic は SSE 形式 (event:/data: プレフィックス) で返す
                current_event_type: str | None = None
                current_data: str = ""
                usage_buffer: dict[str, int] = {}
                stop_reason_buffer: str | None = None

                # ツール呼び出しの蓄積用バッファ
                tool_use_meta: dict[str, str] | None = (
                    None  # {"id": "...", "name": "..."}
                )
                json_parts: list[str] = []  # input_json_delta の蓄積

                async for line in response.aiter_lines():
                    line = line.strip()

                    # 空行はスキップ（SSEのイベント境界）
                    if not line:
                        if current_event_type and current_data:
                            # イベントが完全に収集されたのでパース
                            try:
                                event = json.loads(current_data)
                                event_type = current_event_type

                                # エラーイベント
                                if event_type == "error":
                                    yield StreamChunk(
                                        type="error",
                                        error=event.get("error", {}).get(
                                            "message", "Unknown error"
                                        ),
                                    )
                                    return

                                # テキストデルタ
                                elif event_type == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield StreamChunk(type="delta", delta=text)

                                    # ツール呼び出しのパラメータデルタ
                                    elif delta.get("type") == "input_json_delta":
                                        # パラメータの一部を受信、バッファに蓄積
                                        partial_json = delta.get("partial_json", "")
                                        if partial_json:
                                            json_parts.append(partial_json)

                                # ツール呼び出しの開始
                                elif event_type == "content_block_start":
                                    block = event.get("content_block", {})
                                    if block.get("type") == "tool_use":
                                        # ツール呼び出しのメタデータを保存
                                        tool_use_meta = {
                                            "id": block.get("id", ""),
                                            "name": block.get("name", ""),
                                        }
                                        json_parts = []  # JSONバッファをリセット

                                # ツール呼び出しの完了
                                elif event_type == "content_block_stop":
                                    # ツール呼び出しが完了したら、完全な情報を yield
                                    if tool_use_meta and json_parts:
                                        # JSONパーツを結合してパース
                                        try:
                                            full_json = "".join(json_parts)
                                            parameters = json.loads(full_json)

                                            # tool_call チャンクを発行
                                            yield StreamChunk(
                                                type="tool_call",
                                                tool_calls=[
                                                    ToolCall(
                                                        id=tool_use_meta["id"],
                                                        name=tool_use_meta["name"],
                                                        parameters=parameters,
                                                    )
                                                ],
                                            )

                                            # バッファをクリア
                                            tool_use_meta = None
                                            json_parts = []
                                        except json.JSONDecodeError:
                                            logger.warning(
                                                "Failed to parse tool input JSON"
                                            )
                                            tool_name = tool_use_meta.get(
                                                "name", "unknown"
                                            )
                                            error_msg = (
                                                f"Failed to parse tool input JSON "
                                                f"for tool '{tool_name}'"
                                            )
                                            yield StreamChunk(
                                                type="error", error=error_msg
                                            )
                                            tool_use_meta = None
                                            json_parts = []
                                    elif tool_use_meta:
                                        # JSONがない場合も処理（空のパラメータ）
                                        yield StreamChunk(
                                            type="tool_call",
                                            tool_calls=[
                                                ToolCall(
                                                    id=tool_use_meta["id"],
                                                    name=tool_use_meta["name"],
                                                    parameters={},
                                                )
                                            ],
                                        )
                                        tool_use_meta = None

                                # メッセージ開始（prompt tokens を収集）
                                elif event_type == "message_start":
                                    if (
                                        "message" in event
                                        and "usage" in event["message"]
                                    ):
                                        # message_start の usage（input_tokens）を収集
                                        usage_buffer.update(event["message"]["usage"])

                                # メッセージデルタ（stop_reason と usage を収集）
                                elif event_type == "message_delta":
                                    delta = event.get("delta", {})
                                    if "stop_reason" in delta:
                                        stop_reason_buffer = delta["stop_reason"]
                                    if "usage" in event:
                                        # message_delta の usage をマージ
                                        usage_buffer.update(event["usage"])

                                # メッセージの完了
                                elif event_type == "message_stop":
                                    # message_delta で蓄積した情報を使用
                                    finish_reason = stop_reason_buffer or "end_turn"
                                    usage = usage_buffer
                                    yield StreamChunk(
                                        type="done",
                                        finish_reason=finish_reason,
                                        usage={
                                            "prompt_tokens": usage.get(
                                                "input_tokens", 0
                                            ),
                                            "completion_tokens": usage.get(
                                                "output_tokens", 0
                                            ),
                                            "total_tokens": usage.get("input_tokens", 0)
                                            + usage.get("output_tokens", 0),
                                        },
                                    )
                                    return

                            except json.JSONDecodeError:
                                logger.warning(
                                    "Failed to parse SSE data: %s", current_data
                                )

                            # イベントをリセット
                            current_event_type = None
                            current_data = ""
                        continue

                    # event: ... 行
                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                    # data: ... 行
                    elif line.startswith("data:"):
                        data_line = line[5:].strip()
                        # SSE仕様：複数のdata行は改行で連結
                        if current_data:
                            current_data += "\n" + data_line
                        else:
                            current_data = data_line
