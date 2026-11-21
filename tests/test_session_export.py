import json
import pytest
from xinhai.adapters.session_export import parse_import_messages, summary_segments


def test_codex_exec_replay_only_derives_completed_message():
    completed = {'type': 'item.completed', 'item': {
        'id': 'item_0', 'type': 'agent_message', 'text': '首段' + '测试内容' * 250 + '末段',
    }}
    events = [{'type': 'thread.started', 'thread_id': 'synthetic'},
              {'type': 'turn.started'},
              {'type': 'item.updated', 'item': {**completed['item'], 'text': ' partial '}},
              completed, completed]
    raw = '\n'.join(map(json.dumps, events))
    segments = summary_segments(parse_import_messages(raw, 'codex', 'codex-exec-jsonl'))
    assert ''.join(segment for _, segment, _ in segments) == completed['item']['text']
    assert {source['source_line'] for _, _, source in segments} == {4}
    with pytest.raises(ValueError, match='no completed'):
        parse_import_messages('\n'.join(map(json.dumps, events[:3])), 'codex', 'codex-exec-jsonl')
from xinhai.adapters.session_export import parse_session_export

@pytest.mark.parametrize('client',['codex','cursor'])
def test_explicit_export_preserves_speakers_and_unknown_fields(client):
    messages=[{'speaker':'user','text':'好的','event_id':'e1'},{'speaker':'assistant','text':'结果待核验','extra':True}]
    raw=json.dumps({'format':'xinhai-session-v1','client_type':client,'messages':messages})
    assert parse_session_export(raw,client)==messages
    with pytest.raises(ValueError): parse_session_export(raw,'cursor' if client=='codex' else 'codex')

def test_retry_screen_is_conservative_and_does_not_mutate_original():
    from xinhai.adapters.session_export import screen_messages
    messages=[{'speaker':'user','text':'继续推进','event_id':'1'},
              {'speaker':'user','text':'继续推进','event_id':'1'},
              {'speaker':'user','text':'继续推进'},
              {'speaker':'system','text':'Reconnecting 2/5'},
              {'speaker':'user','text':'Reconnecting 2/5 导致测试失败'},
              {'speaker':'user','text':'换一句话','event_id':'1'}]
    result=screen_messages(messages)
    assert [m['screen_status'] for m in result]==['keep','duplicate','needs_review','transient','keep','needs_review']
    assert all('screen_status' not in m for m in messages)
    from xinhai.adapters.session_export import summary_segments
    segments=summary_segments(messages)
    assert [x[2]['message_index'] for x in segments]==[0,2,4,5]
    assert segments[1][2]['screen_status']=='needs_review'
    assert segments[0][2]['offset_basis']=='message_text'
