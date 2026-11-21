"""Deterministic Chinese-aware chunking; preserves source text before summarization."""
import re

def split_text(text: str, *, max_chars: int = 500, overlap: int = 40) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text: return []
    if len(text) <= max_chars: return [text]
    units = [u.strip() for u in re.split(r"(?<=[。！？；\n])", text) if u.strip()]
    chunks, current = [], ""
    for unit in units:
        if current and len(current) + len(unit) > max_chars:
            chunks.append(current)
            current = current[-overlap:] + unit if overlap else unit
        else: current += unit
    if current: chunks.append(current)
    return chunks
