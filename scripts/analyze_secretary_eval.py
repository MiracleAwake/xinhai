"""Summarize Secretary evaluation errors without touching the memory DB."""
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    groups = defaultdict(Counter)
    examples = defaultdict(list)
    for row in report.get('rows', []):
        expected = row.get('expected')
        output = row.get('output') or {}
        got = output.get('memory_layer')
        if expected == 'reject':
            key = 'noise_accepted' if output else 'noise_error'
        elif expected == 'unknown':
            key = 'unknown_not_preserved' if got != 'unknown' else 'unknown_ok'
        elif not row.get('valid'):
            key = 'schema_or_enum_invalid'
        elif row.get('match'):
            key = 'layer_ok'
        else:
            key = 'layer_mismatch'
        groups[expected][key] += 1
        if key not in {'layer_ok', 'unknown_ok'} and len(examples[key]) < 5:
            examples[key].append({'id': row.get('id'), 'text': row.get('text'), 'got': got, 'expected': expected})
    out = {
        'source': args.report,
        'total': report.get('total', len(report.get('rows', []))),
        'schema_rate': report.get('schema_rate'),
        'layer_accuracy': report.get('layer_accuracy'),
        'by_expected': {k: dict(v) for k, v in groups.items()},
        'examples': dict(examples),
        'recommendations': [
            'Keep exact short acknowledgements and tool-progress messages before model invocation.',
            'Keep deterministic layer selection authoritative; use model output only for summary/tags draft.',
            'Add explicit unknown/uncertainty handling for content without evidence or a decision.',
            'Expand rule vocabulary with project-specific terms, then rerun the same fixed v2 set.',
        ],
    }
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': args.output, 'groups': out['by_expected']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
