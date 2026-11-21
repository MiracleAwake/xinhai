from xinhai.service import MemoryService

def test_vector_failure_preserves_original_and_retry_is_idempotent(tmp_path):
    class Provider:
        dimensions=3
        broken=True
        def embed(self,texts):
            if self.broken: raise RuntimeError('offline')
            return [[1.,0.,0.] for _ in texts]
    provider=Provider()
    s=MemoryService(tmp_path/'recovery.sqlite',embedding_provider=provider)
    r=s.remember('完成向量失败恢复验证',branch_id='A')
    assert r.record['vector_status']=='pending'
    rid=r.record['id']
    assert s.store.history(record_id=rid)[0]['text']=='完成向量失败恢复验证'
    provider.broken=False
    assert s.retry_vector(rid)=='ready'
    assert s.retry_vector(rid)=='ready'
    assert s.store.conn.execute('SELECT count(*) FROM record_vectors WHERE record_id=?',(rid,)).fetchone()[0]==1
    s.close()
