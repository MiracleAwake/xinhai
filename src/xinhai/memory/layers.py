from pathlib import Path
import re

class LayerRegistry:
    def __init__(self, path: str | Path):
        self.layers = {}
        current = None
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            m = re.match(r'\s*- id:\s*(\S+)', line)
            if m: current = {}; self.layers[m.group(1)] = current; current['id'] = m.group(1); continue
            m = re.match(r'\s+(name|description|scope|markdown_path):\s*(.+)', line)
            if m and current is not None: current[m.group(1)] = m.group(2).strip()
    def get(self, layer_id):
        if layer_id not in self.layers: raise KeyError(layer_id)
        return self.layers[layer_id]
