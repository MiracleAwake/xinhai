import json
import os
from pathlib import Path
import subprocess
import sys


def test_stdio_rejects_modern_probe_and_accepts_legacy_initialize(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ, "PYTHONPATH": str(root / "src"),
        "XINHAI_ROOT": str(tmp_path), "XINHAI_DB": str(tmp_path / "test.sqlite"),
        "XINHAI_LAYERS": str(root / "config" / "memory_layers.yaml"),
        "XINHAI_MARKDOWN_ROOT": str(tmp_path / "markdown"),
        "XINHAI_CONFIG_ROOT": str(tmp_path / "versions"),
        "XINHAI_MODEL_PROVIDER": "", "XINHAI_EMBEDDING_PROVIDER": "",
    }
    messages = [
        {"id": 0, "method": "server/discover", "params": {}},
        {"id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "probe", "version": "1"},
        }},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "xinhai.mcp_server"], env=env,
        input="".join(json.dumps({"jsonrpc": "2.0", **m}) + "\n" for m in messages),
        text=True, encoding="utf-8", capture_output=True, timeout=10, check=True,
    )
    responses = {row["id"]: row for row in map(json.loads, result.stdout.splitlines())}
    assert responses[0]["error"]["code"] == -32601
    assert responses[1]["result"]["serverInfo"]["name"] == "xinhai-memory"
    assert "ValidationError" not in result.stderr
