from fastapi.testclient import TestClient

from xinhai.api import create_app
from xinhai.mcp_server import MemoryMCPAdapter
from xinhai.service import MemoryService


IDENTITY = {"workspace_id": "rehearsal", "agent_id": "codex", "branch_id": "a"}


def test_summary_revision_and_verification_keep_provenance(tmp_path):
    class Provider:
        calls = 0

        def extract(self, text):
            self.calls += 1
            return {"summary": "revised guidance", "uncertainty": "pending corroboration"}

    provider = Provider()
    service = MemoryService(tmp_path / "maintenance.sqlite", model_provider=provider)
    try:
        old = service.store.remember(**IDENTITY, text="original guidance")
        evidence = service.store.remember(**IDENTITY, text="independent evidence")
        foreign = service.store.remember(**{**IDENTITY, "branch_id": "b"}, text="foreign evidence")
        with TestClient(create_app(MemoryMCPAdapter(service))) as client:
            route = f"/memory-maintenance/{old['id']}"
            body = {**IDENTITY, "request_id": "rehearsal-1"}
            result = client.post(route + "/summary-drafts", json=body)
            assert result.status_code == 200
            draft = result.json()
            assert draft["status"] == "candidate" and draft["text"] == "revised guidance"
            assert client.post(route + "/summary-drafts", json=body).json()["id"] == draft["id"]
            assert provider.calls == 1
            assert service.store.history(record_id=old["id"])[0]["status"] == "active"
            draft_route = f"/memory-maintenance/{draft['id']}"
            provenance = client.get(draft_route, params=IDENTITY).json()
            relation, = provenance["relations"]
            assert relation["type"] == "covers" and relation["to_id"] == old["id"]
            assert relation["metadata"]["end"] == len(old["text"])
            assert provenance["events"][0]["details"]["is_verified"] is False
            covers = {**IDENTITY, "sources": [
                {"record_id": evidence["id"], "start": 0, "end": 5},
                {"record_id": evidence["id"], "start": 12, "end": 20},
            ]}
            invalid = {**covers, "sources": [*covers["sources"],
                       {"record_id": foreign["id"], "start": 0, "end": 5}]}
            assert client.post(draft_route + "/covers", json=invalid).status_code == 404
            assert client.get(draft_route, params=IDENTITY).json()["relations"] == [relation]
            for _ in range(2):
                assert client.post(draft_route + "/covers", json=covers).status_code == 200
            relations = client.get(draft_route, params=IDENTITY).json()["relations"]
            assert {link["to_id"] for link in relations} == {old["id"], evidence["id"]}
            additional = next(link for link in relations if link["to_id"] == evidence["id"])
            assert additional["metadata"]["ranges"] == [{"start": 0, "end": 5}, {"start": 12, "end": 20}]
            revision = {**IDENTITY, "replacement_id": draft["id"], "reason": "explicit review"}
            assert client.post(route + "/supersede", json=revision).status_code == 200
            assert client.post(route + "/supersede", json=revision).status_code == 200
            matches = client.get("/memories/search", params={**IDENTITY, "q": "original guidance"}).json()
            assert old["id"] not in {match["id"] for match in matches}
            current = client.get("/memories/search", params={**IDENTITY, "q": "revised guidance"}).json()
            assert draft["id"] in {match["id"] for match in current}
            previous = service.store.history(record_id=old["id"])[0]
            assert previous["status"] == "obsolete" and previous["text"] == old["text"]
            relation, = client.get(route, params=IDENTITY).json()["relations"]
            assert relation["from_id"] == draft["id"] and relation["type"] == "supersedes"
            review = {**IDENTITY, "evidence_id": evidence["id"], "verifier": "reviewer",
                      "conclusion": "supported", "reason": "independent corroboration"}
            assert client.post(draft_route + "/verify", json={**review, "evidence_id": foreign["id"]}).status_code == 404
            assert client.post(draft_route + "/verify", json=review).status_code == 200
            event = client.get(draft_route, params=IDENTITY).json()["events"][0]
            assert event["action"] == "verify" and event["actor"] == "reviewer"
            assert event["details"]["evidence_id"] == evidence["id"]
    finally:
        service.close()


def test_vector_rebuild_only_processes_requested_branch(tmp_path):
    class Embedding:
        dimensions = 2
        fail = True

        def embed(self, texts):
            if self.fail:
                self.fail = False
                raise TimeoutError("temporary provider failure")
            return [[1.0, 0.0] for _ in texts]

    service = MemoryService(tmp_path / "vectors.sqlite", embedding_provider=Embedding())
    try:
        records = [service.store.remember(**IDENTITY, text=f"record {number}") for number in range(2)]
        service.store.remember(**{**IDENTITY, "branch_id": "b"}, text="other branch")
        with TestClient(create_app(MemoryMCPAdapter(service))) as client:
            route = "/memory-maintenance/vectors"
            failed = client.post(route, json={**IDENTITY, "limit": 1}).json()
            assert failed["results"][0]["status"] == "pending"
            first = client.post(route, json={**IDENTITY, "limit": 1}).json()
            assert first["results"][0]["record_id"] == failed["results"][0]["record_id"]
            second = client.post(route, json={**IDENTITY, "after": first["next_after"]}).json()
            assert second["next_after"] is None
            assert {r["record_id"] for r in first["results"] + second["results"]} == {r["id"] for r in records}
            assert all(r["status"] == "ready" for r in first["results"] + second["results"])
    finally:
        service.close()
