from dataclasses import dataclass
import re
@dataclass(frozen=True)
class RecallDecision:
 should_recall: bool
 query: str
 reasons: tuple[str,...]
 confidence: str

def detect(text: str) -> RecallDecision:
 t=text.strip(); reasons=[]
 if re.search(r'之前|上次|以前|还记得|我们定|曾经|历史|回忆|上回',t): reasons.append('historical_reference')
 if re.search(r'继续|接着|恢复|未完成|待办|上次做到',t): reasons.append('continuation')
 if re.search(r'为什么|当时|原话|依据|哪天|哪次',t): reasons.append('evidence_request')
 should=bool(reasons)
 # Keep the original query for audit, but provide a normalized keyword query
 # for callers that need a second, less literal retrieval pass.
 cleaned=re.sub(r'^(接着|继续|恢复|回到|参考|按照)(上次|之前|刚才|那个|那条)?','',t).strip()
 cleaned=re.sub(r'(的)?(验收句子|那句话|那条内容|这个问题)$','',cleaned).strip()
 query=cleaned or t
 query=re.sub(r'^的+','',query).strip() or t
 return RecallDecision(should,query,tuple(reasons),'high' if len(reasons)>=2 else ('medium' if should else 'low'))
