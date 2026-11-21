"""Launch an interactive Codex probe against a fresh, isolated database."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = Path(tempfile.mkdtemp(prefix='deepsea-codex-probe-')).resolve()
    shutil.copyfile(root / 'config' / 'memory_layers.yaml', folder / 'layers.yaml')
    env = {
        'PYTHONPATH': str(root / 'src'),
        'XINHAI_ROOT': str(folder),
        'XINHAI_DB': str(folder / 'probe.sqlite'),
        'XINHAI_LAYERS': str(folder / 'layers.yaml'),
        'XINHAI_MARKDOWN_ROOT': str(folder / 'markdown'),
        'XINHAI_CONFIG_ROOT': str(folder / 'config'),
        'XINHAI_MODEL_PROVIDER': '',
        'XINHAI_EMBEDDING_PROVIDER': '',
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    print(f'Temporary probe directory: {folder}', flush=True)
    if args.prepare_only:
        print(json.dumps(env, ensure_ascii=False, indent=2))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error('launch from an interactive terminal to review MCP approval prompts')
    encode = lambda value: json.dumps(value, ensure_ascii=False)
    env_table = ','.join(f'{key}={encode(value)}' for key, value in env.items())
    config = (
        'mcp_servers={xinhai_isolated={command=' + encode(sys.executable)
        + ',args=["-m","xinhai.mcp_server"],env={' + env_table + '},startup_timeout_sec=30}}'
    )
    prompt = (
        'Validate only the temporary xinhai_isolated MCP server. Request normal approval. '
        'Remember synthetic text "DeepSea host probe", user_confirmed=true, '
        'workspace_id=acceptance, agent_id=codex-probe, branch_id=probe-a. '
        'Recall the same text and identity, then recall with branch_id=probe-b. '
        'Report the write record ID, the same-branch ID and the other-branch result. '
        'If approval is unavailable, report that and stop without substitutes.'
    )
    return subprocess.call([
        'codex', '--no-daemon', '--ignore-user-config', '--ignore-rules',
        '--ask-for-approval', 'on-request', '--sandbox', 'workspace-write',
        '-c', config, prompt,
    ], cwd=folder)


if __name__ == '__main__':
    raise SystemExit(main())
