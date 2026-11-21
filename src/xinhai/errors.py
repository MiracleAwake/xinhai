from dataclasses import dataclass
from typing import Any
@dataclass
class XinhaiError(Exception):
 code:str; message:str; retryable:bool=False; record_id:str|None=None; status_code:int=400; details:Any=None
 def envelope(self,request_id=None): return {'ok':False,'error':{'code':self.code,'message':self.message,'retryable':self.retryable,'request_id':request_id,'record_id':self.record_id,'details':self.details}}
class RecordNotFound(XinhaiError):
 def __init__(self,record_id): super().__init__('RECORD_NOT_FOUND',f'record not found: {record_id}',False,record_id,404)
class InvalidWeights(XinhaiError, ValueError):
 def __init__(self): super().__init__('INVALID_WEIGHTS','provide both positive finite text_weight and vector_weight',status_code=422)
class ScopeDenied(XinhaiError):
 def __init__(self): super().__init__('SCOPE_DENIED','memory scope denied',False,None,403)
class DatabaseBusy(XinhaiError):
 def __init__(self): super().__init__('DATABASE_BUSY','database is busy; retry later',True,None,503)
