"""Deterministic evaluation harness placeholder for candidate embeddings."""
import json
from pathlib import Path

def load_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))

def recall_at_k(results: list[str], relevant: set[str], k: int = 5) -> float:
    return 1.0 if any(x in relevant for x in results[:k]) else 0.0

def lexical_baseline(manifest: dict) -> dict:
    """Keyword baseline over OCR + visual summary; used before real embeddings."""
    rows={s['id']:(s.get('ocr','')+' '+s.get('summary','')) for s in manifest['samples']}
    scores=[]
    for q in manifest['queries']:
        hits=[sid for sid,text in rows.items() if q['text'] in text]
        scores.append(recall_at_k(hits,set(q['relevant'])))
    return {'method':'ocr+summary-lexical','recall_at_5':sum(scores)/len(scores) if scores else 0.0}

if __name__ == '__main__':
    p=Path(__file__).parents[1]/'tests/fixtures/multimodal_eval_manifest.json'
    m=load_manifest(p)
    print(f"loaded {len(m['samples'])} samples and {len(m['queries'])} queries")
    print(json.dumps(lexical_baseline(m),ensure_ascii=False))
