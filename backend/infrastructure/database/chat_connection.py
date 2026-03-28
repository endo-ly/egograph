"""チャット履歴用SQLite接続管理。

ローカルファイルベースのSQLite接続で、スレッドとメッセージの永続化を担当します。
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# チャット履歴DBのパス（backend/data/chat.sqlite）
DB_PATH = Path(__file__).parent.parent.parent / "data" / "chat.sqlite"


class ChatSQLiteConnection:
    """チャット履歴用のSQLite接続マネージャー。

    コンテキストマネージャーとして使用し、ローカルファイルベースの
    SQLite接続を作成します。WALモードと外部キー制約を有効化します。

    Example:
        >>> with ChatSQLiteConnection() as conn:
        ...     result = conn.execute(
        ...         "SELECT * FROM threads WHERE user_id = ?",
        ...         ("default_user",)
        ...     )
        ...     threads = result.fetchall()
    """

    def __init__(self):
        """ChatSQLiteConnectionを初期化します。"""
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        """コンテキストマネージャーのエントリー。

        データディレクトリを作成し、ローカルファイルベースの
        SQLite接続を開きます。WALモードと外部キー制約を有効化します。

        Returns:
            sqlite3.Connection: 開かれたSQLiteコネクション

        Raises:
            sqlite3.Error: SQLite接続に失敗した場合
        """
        # データディレクトリを作成（存在しない場合）
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Opening chat database at path: %s", DB_PATH)

        # ローカルファイルベースの接続を作成
        # check_same_thread=False: FastAPIの非同期処理で複数スレッドからアクセス可能にする
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # WALモードと外部キー制約を有効化
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

        return self.conn

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """コンテキストマネージャーの終了。

        接続をクローズします。
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Closed chat database connection")


def _create_threads_table(conn: sqlite3.Connection):
    """threadsテーブルとインデックスを作成します。

    Args:
        conn: SQLiteコネクション
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            thread_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_message_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_last_message
        ON threads(user_id, last_message_at DESC)
    """)


def _ensure_model_name_column(conn: sqlite3.Connection) -> None:
    """model_nameカラムが存在することを保証します。"""
    result = conn.execute("PRAGMA table_info(messages)").fetchall()
    columns = [row[1] for row in result]

    if "model_name" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN model_name TEXT")
        logger.info("Added model_name column to messages table")


def _create_messages_table(conn: sqlite3.Connection):
    """messagesテーブルとインデックスを作成します。

    Args:
        conn: SQLiteコネクション
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            model_name TEXT
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_thread_created
        ON messages(thread_id, created_at)
    """)


def create_chat_tables(conn: sqlite3.Connection):
    """チャット履歴用のテーブルを作成します。

    threads テーブルとmessages テーブルを作成し、
    必要なインデックスを設定します。べき等な操作です。

    Args:
        conn: SQLiteコネクション

    Raises:
        sqlite3.Error: テーブル作成に失敗した場合
    """
    logger.info("Creating chat tables if they do not exist")

    _create_threads_table(conn)
    _create_messages_table(conn)
    _ensure_model_name_column(conn)

    conn.commit()
    logger.info("Chat tables created successfully")
