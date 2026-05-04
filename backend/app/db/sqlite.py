import aiosqlite
from app.core.config import settings

_db_path = settings.sqlite_path


async def get_sqlite() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(_db_path)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_sqlite() -> None:
    """Create raw signals table in SQLite."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS raw_signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id   TEXT NOT NULL,
                component_id TEXT NOT NULL,
                severity    TEXT NOT NULL,
                message     TEXT,
                payload     TEXT,
                work_item_id TEXT,
                received_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_component ON raw_signals(component_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_work_item ON raw_signals(work_item_id)"
        )
        await db.commit()
