"""Validate the Codex/Cursor configuration contract fixture itself."""
import json, sys
from pathlib import Path

def main(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    assert data['scope']=='codex-cursor' and data['cases']
    ids={c['id'] for c in data['cases']}
    assert {'empty','active','history_redacted','readonly','fallback'} <= ids
    history=next(c for c in data['cases'] if c['id']=='history_redacted')
    assert 'config' in history['expect']['omit']
    print(json.dumps({'fixture': str(path), 'cases': len(data['cases']), 'valid': True}, ensure_ascii=False))

if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else 'data/evaluation/config_runtime_contract_v1.json')
