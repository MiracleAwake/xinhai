from dataclasses import dataclass, asdict
from typing import Any
@dataclass(frozen=True)
class InternalEvent:
 event_id:str; client_type:str; session_id:str|None; thread_id:str|None; turn:int|None; speaker:str; event_kind:str; text:str|None; timestamp:str|None; tool_name:str|None=None; tool_result:Any=None; raw_ref:str|None=None; unmapped:tuple[str,...]=(); agent_id:str|None=None; workspace_id:str|None=None; branch_id:str|None=None; task_id:str|None=None
 def to_dict(self):return asdict(self)
