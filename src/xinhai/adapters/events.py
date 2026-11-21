from dataclasses import dataclass
from ..domain.events import InternalEvent

@dataclass(frozen=True)
class AdapterCapabilities:
    client_type: str
    has_session: bool = False
    has_thread: bool = False
    has_compaction_hook: bool = False
    has_raw_ref: bool = False

class ClientAdapter:
    capabilities = AdapterCapabilities('unknown')
    def normalize(self, raw: dict) -> InternalEvent:
        raise NotImplementedError
    def denormalize(self, event: InternalEvent) -> dict:
        return event.to_dict()

class GenericAdapter(ClientAdapter):
    def __init__(self, client_type: str): self.capabilities=AdapterCapabilities(client_type)
    def normalize(self, raw: dict) -> InternalEvent:
        known={'event_id','session_id','thread_id','turn','speaker','event_kind','text','timestamp','tool_name','tool_result','raw_ref'}
        missing=tuple(k for k in ('event_id','event_kind','speaker') if not raw.get(k))
        unmapped=tuple(k for k in raw if k not in known)
        return InternalEvent(event_id=str(raw.get('event_id','unknown')), client_type=self.capabilities.client_type, session_id=raw.get('session_id'), thread_id=raw.get('thread_id'), turn=raw.get('turn'), speaker=raw.get('speaker','unknown'), event_kind=raw.get('event_kind','unmapped'), text=raw.get('text'), timestamp=raw.get('timestamp'), tool_name=raw.get('tool_name'), tool_result=raw.get('tool_result'), raw_ref=raw.get('raw_ref'), unmapped=tuple(sorted(set(unmapped+missing))))

class HarnessAdapter(GenericAdapter):
    def __init__(self): super().__init__('harness')
class CursorAdapter(GenericAdapter):
    def __init__(self): super().__init__('cursor')
class CodexAdapter(GenericAdapter):
    def __init__(self): super().__init__('codex')
class WorkBuddyAdapter(GenericAdapter):
    def __init__(self): super().__init__('workbuddy')

class DSHAdapter(GenericAdapter):
    """Maps documented Harness event envelopes; payload details remain versioned fixtures."""
    def __init__(self): super().__init__('dsh')
    def normalize(self, raw: dict) -> InternalEvent:
        kind=raw.get('type') or raw.get('event_type') or 'unmapped'
        payload=raw.get('payload') or raw.get('data') or {}
        event_kind={'session/message':'message','tool/call':'tool_call','tool/result':'tool_result','compaction/start':'compaction','compaction/summary':'compaction','compaction/end':'compaction','hook/invoked':'hook','hook/result':'hook'}.get(kind,kind)
        merged={**payload, 'event_id':raw.get('id') or raw.get('event_id') or payload.get('id'), 'event_kind':event_kind, 'session_id':raw.get('session_id') or payload.get('session_id'), 'thread_id':raw.get('thread_id') or payload.get('thread_id'), 'timestamp':raw.get('timestamp') or payload.get('timestamp'), 'raw_ref':raw.get('seq') or payload.get('seq')}
        if event_kind=='message' and not merged.get('text'): merged['text']=payload.get('content') or payload.get('message')
        if event_kind=='tool_result' and not merged.get('tool_result'): merged['tool_result']=payload.get('result')
        return super().normalize(merged)
