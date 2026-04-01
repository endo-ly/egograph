"""SystemPromptBuilder のユニットテスト。"""

from backend.usecases.chat.system_prompt_builder import SystemPromptBuilder


def test_system_prompt_includes_current_date_section():
    """現在日時セクションが含まれる。"""

    message = SystemPromptBuilder.build_with_current_date()

    assert message.role == "system"
    assert "# Current Date & Time" in message.content
    assert "現在日時:" in message.content


def test_system_prompt_includes_bootstrap_when_context_exists(tmp_path, monkeypatch):
    """コンテキストがある場合は注入セクションが含まれる。"""

    (tmp_path / "USER.md").write_text("user", encoding="utf-8")

    monkeypatch.setattr(
        "backend.infrastructure.context_files.get_context_dir",
        lambda: tmp_path,
    )

    message = SystemPromptBuilder.build_with_current_date()

    assert "# Workspace Files (injected)" in message.content
    assert "## USER.md" in message.content
    assert "user" in message.content


def test_system_prompt_omits_bootstrap_when_missing(tmp_path, monkeypatch):
    """コンテキストがない場合は注入セクションが出ない。"""

    monkeypatch.setattr(
        "backend.infrastructure.context_files.get_context_dir",
        lambda: tmp_path,
    )

    message = SystemPromptBuilder.build_with_current_date()

    assert "# Workspace Files (injected)" not in message.content
