import argparse
from pathlib import Path
from .service import MemoryService

def main():
    p=argparse.ArgumentParser(prog='xinhai')
    p.add_argument('--db', default='data/xinhai.sqlite'); sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('remember'); r.add_argument('text'); r.add_argument('--layer',default=None)
    q=sub.add_parser('recall'); q.add_argument('query'); q.add_argument('--limit',type=int,default=10)
    args=p.parse_args(); root=Path(args.db).parent.parent; service=MemoryService(args.db, layers_path=root/'config/memory_layers.yaml', markdown_root=root/'记忆库')
    if args.command=='remember': print(service.remember(args.text, layer_id=args.layer, user_confirmed=False))
    if args.command=='recall': print(service.recall(args.query, limit=args.limit))
if __name__ == '__main__': main()
