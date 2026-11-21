# MCP smoke test
$env:PYTHONPATH = "$PSScriptRoot\..\src"
$env:XINHAI_ROOT = (Resolve-Path "$PSScriptRoot\..")
$env:XINHAI_DB = Join-Path $env:TEMP "xinhai-mcp-smoke.sqlite"
$env:XINHAI_LAYERS = Join-Path $env:XINHAI_ROOT "config\memory_layers.yaml"
$env:XINHAI_MARKDOWN_ROOT = Join-Path $env:TEMP "xinhai-mcp-smoke-memory"
python -m pytest -q
