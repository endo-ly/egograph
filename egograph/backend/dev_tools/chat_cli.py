"""インタラクティブなチャットCLIツール。

バックエンドの /v1/chat エンドポイントをテストするための開発ツール。

Usage:
    uv run python -m backend.dev_tools.chat_cli

Features:
    - 会話履歴の自動管理
    - ツール呼び出し情報の可視化
    - Richライブラリによる見やすい出力
    - 矢印キー、履歴サポート（prompt_toolkit）
"""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.tree import Tree

from backend.constants import LLM_REQUEST_TIMEOUT


class ChatSession:
    """チャットセッション管理クラス。

    Attributes:
        base_url: バックエンドAPIのベースURL
        api_key: 認証キー（オプション）
        messages: メッセージ履歴
        console: Richコンソール
        prompt_session: prompt_toolkitセッション
    """

    def __init__(
        self, base_url: str = "http://localhost:8000", api_key: str | None = None
    ):
        """ChatSessionを初期化。

        Args:
            base_url: バックエンドAPIのベースURL
            api_key: 認証キー（オプション）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.messages: list[dict] = []
        self.console = Console()
        self.prompt_session = PromptSession(history=InMemoryHistory())

    async def send_message(self, content: str) -> dict:
        """メッセージを送信し、レスポンスを取得。

        Args:
            content: ユーザーメッセージ

        Returns:
            APIレスポンス

        Raises:
            httpx.HTTPStatusError: HTTPエラーが発生した場合
        """
        # ユーザーメッセージを一時的に作成（成功後に履歴に追加）
        user_message = {"role": "user", "content": content}

        # APIリクエスト（スピナー付き）
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        # 送信するメッセージ配列を確認するためのデバッグ出力
        self.console.print(
            Panel(
                f"{self.messages + [user_message]}",
                title="[bold blue]🧪 Debug: Outgoing Messages",
                border_style="blue",
                padding=(1, 2),
            )
        )

        with Live(
            Spinner("dots", text="[cyan]LLMが考え中...[/cyan]"),
            console=self.console,
            transient=True,
        ):
            async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT) as client:
                # 現在の履歴 + 新しいユーザーメッセージでリクエスト
                response = await client.post(
                    f"{self.base_url}/v1/chat",
                    headers=headers,
                    json={"messages": self.messages + [user_message]},
                )
                response.raise_for_status()
                result = response.json()

        # リクエスト成功後、ユーザーメッセージを履歴に追加
        self.messages.append(user_message)
        return result

    def display_response(self, response: dict) -> None:
        """レスポンスを整形して表示。

        Args:
            response: APIレスポンス
        """
        # アシスタントのメッセージ
        message = response.get("message", {})
        content = message.get("content", "")

        if content:
            self.console.print(
                Panel(
                    Markdown(content),
                    title="[bold green]🤖 Assistant",
                    border_style="green",
                    padding=(1, 2),
                )
            )
        else:
            self.console.print("[dim]（メッセージなし）[/dim]")

        # ツール呼び出し情報
        tool_calls = response.get("tool_calls")
        if tool_calls:
            self._display_tool_calls(tool_calls)

        # 使用量情報
        usage = response.get("usage")
        if usage:
            self._display_usage(usage)

        # メッセージ履歴に追加
        self.messages.append(message)

    def _display_tool_calls(self, tool_calls: list[dict]) -> None:
        """ツール呼び出し情報を表示。

        Args:
            tool_calls: ツール呼び出しのリスト
        """
        self.console.print()
        self.console.print(
            Panel(
                "[bold yellow]⚠️  ツール呼び出しが要求されました[/bold yellow]\n\n"
                "[dim]現在のバックエンドはツール呼び出しを実行しません。\n"
                "フェーズ2でサーバー側ReActループを実装予定です。[/dim]",
                title="Tool Calls Detected",
                border_style="yellow",
            )
        )

        for idx, tc in enumerate(tool_calls, 1):
            table = Table(
                title=f"🔧 Tool Call #{idx}: [cyan]{tc.get('name', 'N/A')}[/cyan]",
                show_header=True,
                header_style="bold magenta",
                border_style="blue",
            )
            table.add_column("Property", style="cyan", width=15)
            table.add_column("Value", style="white")

            table.add_row("ID", tc.get("id", "N/A"))
            table.add_row("Name", tc.get("name", "N/A"))

            # パラメータを見やすく表示
            params = tc.get("parameters", {})
            if params:
                params_str = "\n".join([f"  {k}: {v}" for k, v in params.items()])
                table.add_row("Parameters", params_str)
            else:
                table.add_row("Parameters", "[dim]なし[/dim]")

            self.console.print(table)

    def _display_usage(self, usage: dict) -> None:
        """トークン使用量を表示。

        Args:
            usage: 使用量情報
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # トークン使用量をバー表示
        max_width = 40
        if total_tokens > 0:
            prompt_bar_width = int((prompt_tokens / total_tokens) * max_width)
            completion_bar_width = int((completion_tokens / total_tokens) * max_width)
        else:
            prompt_bar_width = 0
            completion_bar_width = 0

        self.console.print()
        self.console.print("[bold]📊 Token Usage:[/bold]")
        self.console.print(
            f"  Prompt:     [cyan]{'█' * prompt_bar_width}[/cyan] {prompt_tokens:,}"
        )
        self.console.print(
            f"  Completion: [green]{'█' * completion_bar_width}[/green] "
            f"{completion_tokens:,}"
        )
        self.console.print(f"  [bold]Total:      {total_tokens:,}[/bold]")

    def show_history(self) -> None:
        """会話履歴をツリー表示。"""
        if not self.messages:
            self.console.print("[yellow]会話履歴がありません[/yellow]")
            return

        tree = Tree("💬 [bold]Conversation History[/bold]")

        for idx, msg in enumerate(self.messages, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 役割に応じたアイコンと色
            if role == "user":
                emoji = "👤"
                style = "blue"
            elif role == "assistant":
                emoji = "🤖"
                style = "green"
            else:
                emoji = "🔧"
                style = "yellow"

            # 内容のプレビュー（最初の60文字）
            preview = content[:60] + "..." if len(content) > 60 else content
            preview = preview.replace("\n", " ")  # 改行を削除

            branch = tree.add(f"[{style}]{emoji} {role.capitalize()}[/{style}]")
            branch.add(f"[dim]{preview}[/dim]")

        self.console.print(tree)

    def clear_history(self) -> None:
        """会話履歴をクリア。"""
        self.messages.clear()
        self.console.print("[green]✓ 会話履歴をクリアしました[/green]")


async def run_interactive_chat(
    base_url: str = "http://localhost:8000", api_key: str | None = None
):
    """インタラクティブなチャットセッションを実行。

    Args:
        base_url: バックエンドAPIのベースURL
        api_key: 認証キー
    """
    console = Console()
    session = ChatSession(base_url, api_key)

    # ウェルカムメッセージ
    console.print(
        Panel.fit(
            "[bold green]🤖 EgoGraph Chat CLI[/bold green]\n\n"
            "Type your message and press [bold]Enter[/bold].\n"
            "Use [bold cyan]↑/↓[/bold cyan] to navigate history.\n\n"
            "[bold]Commands:[/bold]\n"
            "  [cyan]exit[/cyan]      - Quit\n"
            "  [cyan]/history[/cyan]  - Show conversation tree\n"
            "  [cyan]/clear[/cyan]    - Clear history\n"
            "  [cyan]/help[/cyan]     - Show help",
            border_style="green",
            padding=(1, 2),
        )
    )

    # ヘルスチェック
    try:
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{base_url}/health")
            health.raise_for_status()
            console.print(
                f"[green]✓ Backend is healthy[/green] ({health.json().get('status')})\n"
            )
    except Exception as e:
        console.print(
            Panel(
                f"[red]✗ Backend health check failed[/red]\n\n"
                f"Error: {e}\n\n"
                "Make sure backend is running:\n"
                "[cyan]uv run python -m backend.main[/cyan]",
                title="Connection Error",
                border_style="red",
            )
        )
        return

    # メインループ
    while True:
        try:
            # prompt_toolkitで入力（矢印キー・履歴サポート）
            user_input = await session.prompt_session.prompt_async("👤 You: ")

            if not user_input.strip():
                continue

            # コマンド処理
            if user_input.lower() == "exit":
                console.print("[yellow]👋 Goodbye![/yellow]")
                break
            elif user_input.lower() == "/history":
                session.show_history()
                continue
            elif user_input.lower() == "/clear":
                session.clear_history()
                continue
            elif user_input.lower() == "/help":
                console.print(_get_help_panel())
                continue

            # メッセージ送信
            try:
                response = await session.send_message(user_input)
                session.display_response(response)
            except httpx.HTTPStatusError as e:
                console.print(
                    Panel(
                        (
                            f"[red]HTTP {e.response.status_code}[/red]\n\n"
                            f"{e.response.text}"
                        ),
                        title="API Error",
                        border_style="red",
                    )
                )
            except Exception as e:
                console.print(
                    Panel(
                        f"[red]{type(e).__name__}[/red]\n\n{str(e)}",
                        title="Error",
                        border_style="red",
                    )
                )

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
        except EOFError:
            console.print("\n[yellow]👋 Goodbye![/yellow]")
            break


def _get_help_panel() -> Panel:
    """ヘルプパネルを取得。

    Returns:
        ヘルプパネル
    """
    help_text = """[bold cyan]Available Commands:[/bold cyan]

  [green]exit[/green]         - Quit the chat
  [green]/history[/green]     - Show conversation history as a tree
  [green]/clear[/green]       - Clear conversation history
  [green]/help[/green]        - Show this help message

[bold cyan]Keyboard Shortcuts:[/bold cyan]

  [green]↑/↓[/green]          - Navigate input history
  [green]Ctrl+C[/green]       - Interrupt (doesn't quit)
  [green]Ctrl+D[/green]       - Quit

[bold cyan]Example Messages:[/bold cyan]

  • 先月の再生回数トップ5は？
  • 2025年12月に最も聴いた曲は？
  • 今週の視聴統計を教えて
"""
    return Panel(help_text, title="Help", border_style="cyan", padding=(1, 2))


def main():
    """CLIのエントリーポイント。"""
    # .envファイルを読み込み
    load_dotenv()

    # 環境変数から設定を取得
    backend_host = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port = os.getenv("BACKEND_PORT", "8000")
    api_key = os.getenv("BACKEND_API_KEY")

    full_url = f"http://{backend_host}:{backend_port}"

    # 非同期実行
    try:
        asyncio.run(run_interactive_chat(full_url, api_key))
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
