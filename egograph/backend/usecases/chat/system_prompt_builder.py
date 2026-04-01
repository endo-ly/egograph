"""システムプロンプト構築ロジック。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.infrastructure.context_files import build_bootstrap_context
from backend.infrastructure.llm import Message

JST = ZoneInfo("Asia/Tokyo")


class SystemPromptBuilder:
    """システムプロンプトを構築するクラス。"""

    @staticmethod
    def build_with_current_date() -> Message:
        """現在日時コンテキストを含むシステムプロンプトを構築する。

        Returns:
            Message: システムロールのメッセージ
        """
        now = datetime.now(JST)
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        weekday = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]

        # 汎用アシスタント向けシステムプロンプト
        base_prompt = """
# Tooling
- **使用指針**: ユーザーの記録に基づく質問はツールで事実確認し、推測はしない。
- **非使用指針**: 一般会話や相談はツールなしで自然に応答する。
- **失敗時**: ツールエラーは専門用語を避けて要点のみ伝える。

"""

        sections = [base_prompt.strip()]

        bootstrap_context = build_bootstrap_context()
        if bootstrap_context:
            sections.append(
                "# Workspace Files (injected)\n以下のファイル内容がこの後に続きます。"
            )
            sections.append(bootstrap_context)

        sections.append(
            "# Current Date & Time\n"
            f"- 現在日時: {current_date} ({weekday}) {current_time} JST"
        )

        system_prompt_content = "\n\n".join(sections)

        return Message(
            role="system",
            content=system_prompt_content.strip(),
        )


# Design notes: see docs/30.dev_practices/system_prompt_design.md
