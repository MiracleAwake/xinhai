"""Versioned, validated configuration snapshots for local deployments."""
from __future__ import annotations
import hashlib, json, os, tempfile
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_META = {'config_id', 'version', 'created_at', 'author', 'reason', 'scope', 'parent_version', 'checksum', 'validation_status'}

def weight_arguments(text_weight=None, vector_weight=None):
    import math
    if text_weight is None and vector_weight is None: return {}
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (text_weight,vector_weight)):
        from .errors import InvalidWeights
        raise InvalidWeights()
    return {'weights':{'text':text_weight,'vector':vector_weight}}

class ConfigManager:
    def __init__(self, root):
        self.root = Path(root)
        self.manifests = self.root / 'manifests'
        self.backups = self.root / 'backups'
        self.manifest = self.manifests / 'current.json'
        self.manifests.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def checksum(payload):
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def validate(payload):
        if not isinstance(payload, dict) or not isinstance(payload.get('config'), dict):
            raise ValueError('config snapshot must contain an object config')
        config = payload['config']
        if not config:
            raise ValueError('config must not be empty')
        if not isinstance(payload.get('version'), str) or not payload['version']:
            raise ValueError('version is required')
        if not isinstance(payload.get('scope'), str) or not payload['scope']:
            raise ValueError('scope is required')
        # Never allow a snapshot to disable provenance/isolation invariants.
        forbidden = {'disable_source_tracking', 'disable_branch_isolation', 'drop_original_text'}
        if forbidden & set(config):
            raise ValueError('snapshot attempts to disable a protected invariant')
        return True

    def runtime_options(self):
        """Return only explicitly supported, type-checked runtime options."""
        current=self.current()
        if not current: return {}
        retrieval=current.get('config', {}).get('retrieval', {})
        out={}
        weights=retrieval.get('weights')
        if isinstance(weights, dict) and all(isinstance(weights.get(k), (int,float)) for k in ('text','vector')):
            out['retrieval.weights']={'text':float(weights['text']), 'vector':float(weights['vector'])}
        if isinstance(retrieval.get('reranker'), str): out['retrieval.reranker']=retrieval['reranker']
        if isinstance(retrieval.get('expand_source'), bool): out['retrieval.expand_source']=retrieval['expand_source']
        return out

    def current(self):
        if not self.manifest.exists():
            return None
        return self.read_valid(self.manifest)

    def read_valid(self, path):
        payload=json.loads(Path(path).read_text(encoding='utf-8'))
        self.validate(payload)
        expected=self.checksum({k:v for k,v in payload.items() if k not in {'checksum','validation_status'}})
        if payload.get('checksum') != expected or payload.get('validation_status') != 'valid':
            raise ValueError('invalid configuration snapshot integrity')
        return payload

    def history(self):
        """Return valid snapshots newest-first without exposing config bodies."""
        rows=[]
        for path in self.backups.glob('*.json'):
            try: payload=self.read_valid(path)
            except (OSError, ValueError): continue
            if payload.get('validation_status') != 'valid': continue
            rows.append({k: payload.get(k) for k in ('config_id','version','created_at','author','reason','scope','parent_version','checksum','validation_status')})
        return sorted(rows, key=lambda x: x.get('created_at') or '', reverse=True)

    def stage(self, config, *, version, author='unknown', reason='', scope='project'):
        parent = self.current()
        payload = {
            'config_id': f'{scope}:{version}', 'version': version,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'author': author, 'reason': reason, 'scope': scope,
            'parent_version': parent.get('version') if parent else None,
            'config': config,
        }
        payload['checksum'] = self.checksum(payload)
        payload['validation_status'] = 'valid' if self.validate(payload) else 'invalid'
        return payload

    def activate(self, payload):
        self.validate(payload)
        expected = self.checksum({k: payload[k] for k in payload if k not in {'checksum', 'validation_status'}})
        if payload.get('checksum') != expected:
            raise ValueError('config checksum mismatch')
        if payload.get('validation_status') != 'valid':
            raise ValueError('config snapshot is not valid')
        backup = self.backups / f"{payload['config_id'].replace(':','_')}.json"
        if backup.exists() and self.read_valid(backup) != payload:
            raise ValueError('configuration version already exists with different content')
        backup.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        fd, temp = tempfile.mkstemp(prefix='current.', suffix='.json', dir=self.manifests)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp, self.manifest)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        return payload

    def rollback(self, version=None):
        current=self.current()
        candidates = sorted(self.backups.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            try: payload = self.read_valid(path)
            except (OSError, ValueError): continue
            if not version and current and payload.get('config_id') == current.get('config_id'): continue
            if version and payload.get('version') != version: continue
            if payload.get('validation_status') != 'valid': continue
            self.activate(payload)
            return payload
        raise ValueError('no valid configuration snapshot available for rollback')

    def snapshot(self, version):
        for path in self.backups.glob('*.json'):
            try: payload=self.read_valid(path)
            except (OSError, ValueError): continue
            if payload.get('version') == version and payload.get('validation_status') == 'valid': return payload
        raise ValueError(f'valid configuration version not found: {version}')

    def diff(self, older, newer):
        """Return changed top-level config sections only; never mutate state."""
        a=self.snapshot(older).get('config', {}); b=self.snapshot(newer).get('config', {})
        keys=sorted(set(a) | set(b)); return {k: {'from': self._redact(a.get(k), k), 'to': self._redact(b.get(k), k)} for k in keys if a.get(k) != b.get(k)}

    @staticmethod
    def _redact(value, key=''):
        if re.search(r'(secret|token|password|passwd|api[_-]?key|private[_-]?key)', key, re.I): return '[REDACTED]'
        if isinstance(value, dict): return {k: ConfigManager._redact(v, k) for k,v in value.items()}
        if isinstance(value, list): return [ConfigManager._redact(v, key) for v in value]
        return value
