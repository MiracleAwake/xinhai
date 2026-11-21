"""Manage versioned DeepSea configuration snapshots."""
import argparse, json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from xinhai.configuration import ConfigManager

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='config/versions')
    sub=ap.add_subparsers(dest='command', required=True)
    p=sub.add_parser('stage'); p.add_argument('--file', required=True); p.add_argument('--version', required=True); p.add_argument('--author', default='local'); p.add_argument('--reason', default=''); p.add_argument('--scope', default='project')
    p=sub.add_parser('activate'); p.add_argument('--file', required=True)
    p=sub.add_parser('rollback'); p.add_argument('--version')
    p=sub.add_parser('diff'); p.add_argument('--older', required=True); p.add_argument('--newer', required=True)
    sub.add_parser('current')
    a=ap.parse_args(); m=ConfigManager(a.root)
    if a.command=='stage':
        config=json.loads(Path(a.file).read_text(encoding='utf-8'))
        out=m.stage(config,version=a.version,author=a.author,reason=a.reason,scope=a.scope)
        print(json.dumps(out,ensure_ascii=False,indent=2)); return
    if a.command=='activate':
        out=m.activate(json.loads(Path(a.file).read_text(encoding='utf-8'))); print(json.dumps(out,ensure_ascii=False,indent=2)); return
    if a.command=='rollback': out=m.rollback(a.version)
    elif a.command=='diff': out=m.diff(a.older, a.newer)
    else: out=m.current()
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
