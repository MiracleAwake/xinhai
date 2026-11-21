from pathlib import Path

class MarkdownWriter:
    def __init__(self, root: str | Path): self.root = Path(root)
    def append(self, *, layer: dict, record: dict, summary: str, tags: list[str]) -> Path:
        target_dir = self.root / layer['markdown_path']
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / '心海_自动记忆.md'
        marker = f"<!-- xinhai-record:{record['id']} -->"
        if target.exists() and marker in target.read_text(encoding='utf-8'): return target
        block = f"\n{marker}\n## {record['ts']} · {layer['name']}\n\n{summary}\n\n- 记录 ID：`{record['id']}`\n- 说话人：{record['speaker']}\n- 标签：{'、'.join(tags) or '无'}\n- 原文来源：{record.get('source_path') or record.get('session_id') or '未提供'}\n"
        with target.open('a', encoding='utf-8') as f: f.write(block)
        return target
