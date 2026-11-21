"""Explicit exchange format, not a parser for private client storage."""
import json
import re

STRUCTURED_FORMATS = {'xinhai-session-v1', 'codex-session-jsonl', 'codex-exec-jsonl'}


def parse_import_messages(content, client_type, file_format):
    if file_format == 'xinhai-session-v1':
        return parse_session_export(content, client_type)
    if file_format == 'codex-exec-jsonl' and client_type == 'codex':
        return parse_codex_exec(content)
    if file_format != 'codex-session-jsonl' or client_type != 'codex':
        raise ValueError('unsupported client and session format combination')
    messages = []
    session_header = False
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'expected JSON object at line {line_number}')
        session_header |= row.get('type') == 'session_meta'
        payload = row.get('payload')
        if row.get('type') != 'response_item' or not isinstance(payload, dict):
            continue
        role = payload.get('role')
        if payload.get('type') != 'message' or role not in ('user', 'assistant'):
            continue
        parts = payload.get('content')
        if not isinstance(parts, list):
            raise ValueError(f'invalid message content at line {line_number}')
        chunks = [
            part['text'] for part in parts if isinstance(part, dict)
            and part.get('type') in ('input_text', 'output_text')
            and isinstance(part.get('text'), str)
        ]
        if chunks:
            message = {'speaker': role, 'text': '\n'.join(chunks), 'source_line': line_number}
            if isinstance(payload.get('id'), str) and payload['id']:
                message['event_id'] = payload['id']
            messages.append(message)
    if not session_header or not messages:
        raise ValueError('expected Codex session metadata and supported conversation messages')
    return messages


def parse_codex_exec(content):
    messages = []
    thread_id = None
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'expected JSON object at line {line_number}')
        if row.get('type') == 'thread.started':
            current = row.get('thread_id')
            if not isinstance(current, str) or not current or thread_id not in (None, current):
                raise ValueError('expected a single Codex thread per archive')
            thread_id = current
        item = row.get('item')
        if row.get('type') != 'item.completed' or not isinstance(item, dict):
            continue
        speaker = {'agent_message': 'assistant', 'user_message': 'user'}.get(item.get('type'))
        if speaker is None:
            continue
        event_id, text = item.get('id'), item.get('text')
        if not thread_id or not isinstance(event_id, str) or not event_id or not isinstance(text, str):
            raise ValueError(f'invalid completed Codex message at line {line_number}')
        messages.append({'speaker': speaker, 'text': text, 'event_id': event_id,
                         'source_line': line_number})
    if not messages:
        raise ValueError('no completed Codex conversation message')
    return messages

def screen_messages(messages):
    """Annotate derived input; never modify the archived transcript."""
    seen_ids={}; previous=None; out=[]
    for index,message in enumerate(messages):
        text=message['text']; identity=(message['speaker'],text)
        event_id=message.get('event_id')
        status='keep'; reason=None
        if event_id and event_id in seen_ids:
            status='duplicate' if seen_ids[event_id]==identity else 'needs_review'
            reason='replayed_event_id' if status=='duplicate' else 'event_id_content_conflict'
        elif re.fullmatch(r'\s*(?:Reconnecting|正在重连)\s*\d+\s*/\s*\d+\s*[.…]*\s*',text,re.I):
            status='transient'; reason='connection_progress'
        elif previous==identity:
            status='needs_review'; reason='adjacent_identical_content'
        if event_id: seen_ids.setdefault(event_id,identity)
        out.append({**message,'message_index':index,'screen_status':status,'screen_reason':reason})
        previous=identity
    return out

def summary_segments(messages):
    segments=[]; position=0
    for message in screen_messages(messages):
        text=message['text']
        if message['screen_status'] not in {'duplicate','transient'}:
            for start in range(0,len(text),500):
                segments.append((position+start,text[start:start+500],{
                    'offset_basis':'message_text','message_index':message['message_index'],
                    'message_start':start,'message_end':min(start+500,len(text)),
                    'speaker':message['speaker'],'screen_status':message['screen_status'],
                    **({'source_line':message['source_line']} if 'source_line' in message else {}),
                    'screen_reason':message['screen_reason']}))
        position+=len(text)+1
    return segments

def parse_session_export(content, client_type):
    if client_type not in {'codex','cursor'}: raise ValueError('unsupported client')
    obj=json.loads(content)
    if obj.get('format')!='xinhai-session-v1' or obj.get('client_type')!=client_type:
        raise ValueError('expected explicit xinhai-session-v1 export')
    messages=obj.get('messages')
    if not isinstance(messages,list): raise ValueError('messages must be a list')
    for message in messages:
        if not isinstance(message,dict) or message.get('speaker') not in {'user','assistant','tool','system'} or not isinstance(message.get('text'),str):
            raise ValueError('invalid message; original archive remains available')
    return messages
