"""システムプロンプト用のコンテキストファイル管理。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONTEXT_FILE_MAX_CHARS = 20000
CONTEXT_DIR = Path(__file__).resolve().parent / "context"


@dataclass(frozen=True)
class ContextFile:
    """コンテキストファイルの定義。"""

    key: str
    filename: str


CONTEXT_FILES: list[ContextFile] = [
    ContextFile("user", "USER.md"),
    ContextFile("identity", "IDENTITY.md"),
    ContextFile("soul", "SOUL.md"),
    ContextFile("tools", "TOOLS.md"),
    ContextFile("agents", "AGENTS.md"),
    ContextFile("heartbeat", "HEARTBEAT.md"),
    ContextFile("bootstrap", "BOOTSTRAP.md"),
]

CONTEXT_FILE_MAP = {entry.key: entry for entry in CONTEXT_FILES}


def get_context_dir() -> Path:
    """コンテキストファイルのディレクトリを返します。

    Returns:
        コンテキストディレクトリのパス

    Note:
        設定がない場合は backend/context/ をデフォルトとして使用します。
    """
    return CONTEXT_DIR


def get_templates_dir() -> Path:
    """テンプレートディレクトリを返します。"""

    return get_context_dir() / "templates"


def resolve_context_file(name: str) -> ContextFile:
    """キー名からコンテキストファイルを解決します。"""

    normalized = name.strip().lower()
    entry = CONTEXT_FILE_MAP.get(normalized)
    if entry is None:
        allowed = ", ".join(CONTEXT_FILE_MAP.keys())
        raise ValueError(f"invalid_name: name must be one of {allowed}")
    return entry


def read_context_file(
    name: str,
    *,
    max_chars: int | None = CONTEXT_FILE_MAX_CHARS,
) -> str | None:
    """コンテキストファイルを読み込みます。"""

    entry = resolve_context_file(name)
    context_path = get_context_dir() / entry.filename
    if not context_path.exists():
        return None

    content = context_path.read_text(encoding="utf-8")
    if max_chars is not None and len(content) > max_chars:
        return content[:max_chars]
    return content


def ensure_context_file(name: str) -> str:
    """コンテキストファイルを確実に用意します。"""

    entry = resolve_context_file(name)
    context_dir = get_context_dir()
    context_path = context_dir / entry.filename
    if context_path.exists():
        return context_path.read_text(encoding="utf-8")

    template_path = get_templates_dir() / entry.filename
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        content = ""

    context_dir.mkdir(parents=True, exist_ok=True)
    context_path.write_text(content, encoding="utf-8")
    return content


def write_context_file(
    name: str,
    content: str,
) -> None:
    """コンテキストファイルに書き込みます。"""

    if len(content) > CONTEXT_FILE_MAX_CHARS:
        raise ValueError(
            f"invalid_content: content must be <= {CONTEXT_FILE_MAX_CHARS} characters"
        )
    entry = resolve_context_file(name)
    context_dir = get_context_dir()
    context_dir.mkdir(parents=True, exist_ok=True)
    context_path = context_dir / entry.filename
    context_path.write_text(content, encoding="utf-8")


def build_bootstrap_context() -> str:
    """ブートストラップコンテキストを構築します。"""

    sections: list[str] = []
    for entry in CONTEXT_FILES:
        content = read_context_file(entry.key, max_chars=CONTEXT_FILE_MAX_CHARS)
        if content is None:
            continue
        body = content.strip()
        if body:
            sections.append(f"## {entry.filename}\n{body}")
        else:
            sections.append(f"## {entry.filename}")
    return "\n\n".join(sections)
