"""Drain persisted imports once. Use one local worker per DB."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from xinhai.runtime import adapter_from_env
from xinhai.onboarding import router_for

def main():
    adapter=adapter_from_env()
    try:
        router_for(adapter.service)
        print(json.dumps(adapter.service.run_import_queue(),ensure_ascii=False))
    finally: adapter.service.close()

if __name__=='__main__': main()
