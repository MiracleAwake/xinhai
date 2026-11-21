import re

def parse_firewall_rules(ocr_text: str) -> list[dict]:
    """Extract conservative firewall rows from OCR; never infer missing states."""
    rows=[]
    pat=re.compile(r'(Block Ollama[^\n]*?)\s+(True|False)\s+(Allow|Block)\s+(Inbound|Outbound)',re.I)
    for m in pat.finditer(ocr_text or ''):
        rows.append({'rule_name':m.group(1).strip(),'enabled':m.group(2).lower()=='true','action':m.group(3).title(),'direction':m.group(4).title(),'evidence':m.group(0)})
    return rows
