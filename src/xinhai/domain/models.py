from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class MemoryRecord:
    id: str
    scope: str
    kind: str
    speaker: str
    ts: str
    text: str
    status: str = "active"
    source_path: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
