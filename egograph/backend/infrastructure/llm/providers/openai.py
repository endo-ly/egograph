"""OpenAI/OpenRouterプロバイダー。

OpenAI APIとOpenRouter APIは同じフォーマットを使用するため、
base_urlを変更するだけで両方をサポートできます。
"""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from backend.domain.models.llm import ChatResponse, Message, StreamChunk, ToolCall
from backend.domain.models.tool import Tool
from backend.infrastructure.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI/OpenRouterプロバイダー。

    OpenAI APIフォーマットに準拠したプロバイダーをサポートします。
    """

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str = "https://api.z.ai/api/coding/paas/v4",
        # base_url: str = "https://api.openai.com/v1",
        enable_web_search: bool = False,
    ):
        """OpenAIProviderを初期化します。

        Args:
            api_key: API認証キー
            model_name: モデル名(例: "gpt-4o-mini")
            base_url: APIエンドポイントURL(OpenRouterの場合は変更)
            enable_web_search: Web検索を有効にするか(OpenRouterのみ)
        """
        super().__init__(api_key, model_name)
        self.base_url = base_url.rstrip("/")
        self.enable_web_search = enable_web_search
        self.is_openrouter = "openrouter" in base_url.lower()

    async def chat_completion(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """OpenAI Chat Completion APIを呼び出します。

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
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._convert_messages_to_provider_format(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = self._convert_tools_to_provider_format(tools)

        # OpenRouter固有の設定
        if self.is_openrouter and not self.enable_web_search:
            # Web検索を無効化 (pluginsでwebを無効化)
            payload["plugins"] = [{"id": "web", "enabled": False}]
            logger.debug("OpenRouter: Web search disabled (plugins: web=false)")

        logger.debug("Sending request to %s/chat/completions", self.base_url)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            if response.is_error:
                logger.error(
                    "OpenAI API error: status=%s body=%s",
                    response.status_code,
                    response.text,
                )
            response.raise_for_status()

            return self._parse_response(response.json())

    def _convert_messages_to_provider_format(
        self, messages: list[Message]
    ) -> list[dict]:
        """MessageモデルをOpenAI API形式に変換します。

        Args:
            messages: 統一Message形式のメッセージリスト

        Returns:
            OpenAI API形式のメッセージリスト

        Raises:
            ValueError: role="tool"のメッセージで
                tool_call_idまたはnameが不足している場合
        """
        converted = []
        for msg in messages:
            if msg.role == "tool":
                # tool resultメッセージではtool_call_idとnameが必須
                if not msg.tool_call_id:
                    raise ValueError(
                        "invalid_tool_message: tool_call_id is required for role='tool'"
                    )
                if not msg.name:
                    raise ValueError(
                        "invalid_tool_message: name is required for role='tool'"
                    )

                converted.append(
                    {
                        "role": "tool",
                        "content": msg.content or "",
                        "tool_call_id": msg.tool_call_id,
                        "name": msg.name,
                    }
                )
            elif msg.role == "assistant" and msg.tool_calls:
                # assistantメッセージでtool_callsがある場合
                # ToolCallオブジェクトをOpenAI形式に変換
                converted_tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.parameters),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                message_dict = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": converted_tool_calls,
                }
                converted.append(message_dict)
            else:
                # 通常のメッセージ(user, system, tool_callsのないassistant)
                converted.append({"role": msg.role, "content": msg.content or ""})

        return converted

    def _convert_tools_to_provider_format(self, tools: list[Tool]) -> list[dict]:
        """MCPツールをOpenAI function calling形式に変換します。

        Args:
            tools: MCPツールリスト

        Returns:
            OpenAI形式のツール定義
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools
        ]

    def _parse_response(self, raw: dict) -> ChatResponse:
        """OpenAIレスポンスを統一形式にパースします。

        Args:
            raw: OpenAI APIのレスポンスJSON

        Returns:
            ChatResponse
        """
        choice = raw["choices"][0]
        message = choice["message"]

        # ツール呼び出しのパース
        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                # argumentsはJSON文字列なのでパース
                params = json.loads(tc["function"]["arguments"])
                tool_calls.append(
                    ToolCall(
                        id=tc["id"], name=tc["function"]["name"], parameters=params
                    )
                )

        return ChatResponse(
            id=raw["id"],
            message=Message(
                role=message["role"],
                content=message.get("content", ""),
                tool_calls=tool_calls,
            ),
            tool_calls=tool_calls,
            usage=raw.get("usage"),
            finish_reason=choice["finish_reason"],
        )

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[StreamChunk, None]:
        """OpenAI Chat Completion APIをストリーミングで呼び出します。

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
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._convert_messages_to_provider_format(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,  # ストリーミング有効化
        }

        if tools:
            payload["tools"] = self._convert_tools_to_provider_format(tools)

        # OpenRouter固有の設定
        if self.is_openrouter and not self.enable_web_search:
            payload["plugins"] = [{"id": "web", "enabled": False}]
            logger.debug("OpenRouter: Web search disabled (plugins: web=false)")

        logger.debug("Sending streaming request to %s/chat/completions", self.base_url)

        # ツール呼び出しの引数バッファ: {index: partial_arguments}
        tool_args_buffer: dict[int, str] = {}
        # ツール呼び出しのIDバッファ: {index: tool_call_id}
        tool_id_buffer: dict[int, str] = {}
        # ツール呼び出しの名前バッファ: {index: tool_name}
        tool_name_buffer: dict[int, str] = {}

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            ) as response:
                if response.is_error:
                    body = await response.aread()
                    body_text = body.decode("utf-8", errors="replace")
                    logger.error(
                        "OpenAI API stream error: status=%s body=%s",
                        response.status_code,
                        body_text,
                    )
                    # エラーメッセージを抽出してエラーチャンクをyield
                    try:
                        error_data = json.loads(body_text)
                        # OpenAI/互換APIのエラーフォーマット
                        if "error" in error_data:
                            error_obj = error_data["error"]
                            if isinstance(error_obj, dict):
                                error_message = error_obj.get("message", body_text)
                            else:
                                error_message = str(error_obj)
                        else:
                            error_message = body_text
                    except (json.JSONDecodeError, ValueError):
                        error_message = body_text
                    # エラーチャンクをyieldして終了(例外は投げない)
                    yield StreamChunk(type="error", error=error_message)
                    return

                # SSE パース
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:].strip()

                    # [DONE] マーカー
                    if data_str == "[DONE]":
                        yield StreamChunk(type="done")
                        return

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse SSE line: %s", data_str)
                        continue

                    # チョイスを取得
                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # finish_reason があれば完了
                    if finish_reason:
                        # テキストデルタがある場合は先に yield
                        if "content" in delta and delta["content"]:
                            yield StreamChunk(type="delta", delta=delta["content"])

                        # バッファされたツール呼び出しを yield
                        if tool_args_buffer:
                            tool_calls = []
                            for idx in sorted(tool_args_buffer.keys()):
                                try:
                                    params = json.loads(tool_args_buffer[idx])
                                    tool_calls.append(
                                        ToolCall(
                                            id=tool_id_buffer.get(idx, ""),
                                            name=tool_name_buffer.get(idx, ""),
                                            parameters=params,
                                        )
                                    )
                                except json.JSONDecodeError as err:
                                    logger.warning(
                                        "Failed to parse buffered tool arguments "
                                        "at index %s: %s",
                                        idx,
                                        err,
                                    )
                            if tool_calls:
                                yield StreamChunk(
                                    type="tool_call", tool_calls=tool_calls
                                )

                        yield StreamChunk(
                            type="done",
                            finish_reason=finish_reason,
                            usage=data.get("usage"),
                        )
                        return

                    # テキストデルタ
                    if "content" in delta and delta["content"]:
                        yield StreamChunk(type="delta", delta=delta["content"])

                    # ツール呼び出しのデルタを蓄積
                    # (finish_reasonがない場合でもバッファリングして完了したらyield)
                    if "tool_calls" in delta:
                        tool_calls_delta = delta["tool_calls"]
                        if tool_calls_delta:
                            # OpenAI ストリーミングでは tool_calls は複数チャンクに分割
                            for tc_delta in tool_calls_delta:
                                tc_index = tc_delta.get("index")
                                if tc_index is None:
                                    logger.warning(
                                        "Tool call missing index: %s", tc_delta
                                    )
                                    continue

                                # ツール呼び出しIDを収集
                                if "id" in tc_delta:
                                    tool_id_buffer[tc_index] = tc_delta["id"]

                                # ツール名を収集
                                if (
                                    "function" in tc_delta
                                    and "name" in tc_delta["function"]
                                ):
                                    tool_name_buffer[tc_index] = tc_delta["function"][
                                        "name"
                                    ]

                                # 引数をバッファリング
                                if (
                                    "function" in tc_delta
                                    and "arguments" in tc_delta["function"]
                                ):
                                    args_chunk = tc_delta["function"]["arguments"]
                                    if tc_index not in tool_args_buffer:
                                        tool_args_buffer[tc_index] = args_chunk
                                    else:
                                        tool_args_buffer[tc_index] += args_chunk

                            # バッファされたツール呼び出しをチェックして、完全ならyield
                            if tool_args_buffer:
                                # 一時リストを使用して重複を防止
                                temp_parsed = []
                                all_complete = True

                                for idx in sorted(tool_args_buffer.keys()):
                                    try:
                                        params = json.loads(tool_args_buffer[idx])
                                        temp_parsed.append(
                                            ToolCall(
                                                id=tool_id_buffer.get(idx, ""),
                                                name=tool_name_buffer.get(idx, ""),
                                                parameters=params,
                                            )
                                        )
                                    except json.JSONDecodeError:
                                        # まだ不完全、次のチャンクを待つ
                                        all_complete = False
                                        break

                                # 全てのツール呼び出しが完全ならyield
                                if all_complete and temp_parsed:
                                    yield StreamChunk(
                                        type="tool_call",
                                        tool_calls=temp_parsed,
                                    )
                                    # バッファをクリア
                                    tool_args_buffer.clear()
                                    tool_id_buffer.clear()
                                    tool_name_buffer.clear()

                # ストリームが[DONE]なしで終了した場合のバッファ処理
                if tool_args_buffer:
                    logger.warning(
                        "Stream ended without [DONE] marker, "
                        "flushing buffered tool calls"
                    )
                    tool_calls = []
                    for idx in sorted(tool_args_buffer.keys()):
                        try:
                            params = json.loads(tool_args_buffer[idx])
                            tool_calls.append(
                                ToolCall(
                                    id=tool_id_buffer.get(idx, ""),
                                    name=tool_name_buffer.get(idx, ""),
                                    parameters=params,
                                )
                            )
                        except json.JSONDecodeError as err:
                            logger.warning(
                                "Failed to parse buffered tool arguments "
                                "at index %s: %s",
                                idx,
                                err,
                            )
                    if tool_calls:
                        yield StreamChunk(type="tool_call", tool_calls=tool_calls)
                    # 完了扱いにする
                    yield StreamChunk(type="done", finish_reason="stop")
