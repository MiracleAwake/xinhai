"""Optional local model provider for Memory Secretary.

The provider is deliberately separate from the rule secretary: model failure
must never prevent the deterministic fallback path.
"""
from __future__ import annotations
import json
import urllib.request

class OllamaMemoryProvider:
    def __init__(self, model: str = "qwen2.5vl:3b", host: str = "http://127.0.0.1:11434", timeout: float = 60):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def extract(self, text: str, *, image_b64: str | None = None) -> dict:
        prompt = ("Return JSON only with keys summary,memory_layer,tags,action,uncertainty. "
                  "memory_layer must be one of 工作日志,工作指南,核心记忆节点,经验教训库,工具库,unknown; "
                  "action must be 记录,忽略,待确认. Do not invent facts. "
                  "Do not optimize for brevity by dropping facts, time, causality, source or uncertainty. "
                  "Preserve important details; if unsure, write unknown and keep the relevant wording.\n\n" + text)
        msg = {"role": "user", "content": prompt}
        if image_b64:
            msg["images"] = [image_b64]
        body = json.dumps({"model": self.model, "stream": False, "format": "json", "messages": [msg]}, ensure_ascii=False).encode()
        req = urllib.request.Request(self.host + "/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
        content = payload.get("message", {}).get("content", "")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("model output must be an object")
        return result

def normalize_visual_result(result: dict) -> dict:
    """Normalize multimodal fields without inventing or rewriting content."""
    out=dict(result)
    for key in ('ocr','keywords','uncertainty'):
        value=out.get(key,[])
        if isinstance(value,str): out[key]=[value] if value.strip() else []
        elif isinstance(value,list): out[key]=[str(x) for x in value]
        elif value is None: out[key]=[]
        else: out[key]=[str(value)]
    summary=out.get('visual_summary','')
    out['visual_summary']=summary if isinstance(summary,str) else str(summary or '')
    return out
