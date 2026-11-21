from ..store import MemoryStore

class MemoryGatekeeper:
    def __init__(self, store: MemoryStore, max_chars: int = 2400):
        self.store, self.max_chars = store, max_chars
    def filter(self, records: list[dict], *, allowed_scopes: set[str] | None = None, required_tags: set[str] | None = None):
        allowed_scopes = allowed_scopes or {'personal','workspace','garden'}
        required_tags = required_tags or set()
        out=[]; used=0
        for record in records:
            tags=set(__import__('json').loads(record.get('tags_json','[]')))
            reason=None
            if record.get('scope') not in allowed_scopes: reason='scope_denied'
            elif record.get('status') != 'active': reason='not_active'
            elif required_tags and not required_tags.intersection(tags): reason='tag_mismatch'
            elif used + len(record.get('text','')) > self.max_chars: reason='budget_exceeded'
            if reason:
                action='ignore'
            else:
                action='use'; out.append(record); used += len(record.get('text',''))
            with self.store.conn:
                self.store.conn.execute('INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES (?,?,?,?,?)', (action, record.get('id'), 'gatekeeper', __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), '{"reason":"'+reason+'"}' if reason else '{}'))
        return out
