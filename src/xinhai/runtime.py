from pathlib import Path
import os
from .mcp_server import build_adapter

def adapter_from_env():
    root=Path(os.environ.get('XINHAI_ROOT', Path.cwd()))
    db=Path(os.environ.get('XINHAI_DB', root/'data/xinhai.sqlite'))
    layers=Path(os.environ.get('XINHAI_LAYERS', root/'config/memory_layers.yaml'))
    markdown=Path(os.environ.get('XINHAI_MARKDOWN_ROOT', root/'记忆库'))
    config_root=Path(os.environ.get('XINHAI_CONFIG_ROOT', root/'config'/'versions'))
    return build_adapter(db,layers,markdown,config_root)
