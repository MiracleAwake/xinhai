from pathlib import Path
from ..store import MemoryStore

class SQLiteRepository(MemoryStore):
    """SQLite truth store; compatibility facade kept until full extraction."""
    def __init__(self, path: str | Path):
        super().__init__(path)
