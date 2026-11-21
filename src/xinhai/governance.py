"""Explicit maintenance operations for records in one identity and scope."""

import hashlib
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .errors import RecordNotFound


class RecordScope(BaseModel):
    workspace_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    scope: Literal["personal", "workspace", "garden"] = "personal"

    def values(self):
        return self.workspace_id, self.agent_id, self.branch_id, self.scope


class VectorBatch(RecordScope):
    after: str = ""
    limit: int = Field(default=20, ge=1, le=100)


class SummaryDraft(RecordScope):
    request_id: str = Field(min_length=1)


class Revision(RecordScope):
    replacement_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Verification(RecordScope):
    evidence_id: str = Field(min_length=1)
    verifier: str = Field(min_length=1)
    conclusion: Literal["supported", "contradicted", "inconclusive"]
    reason: str = Field(min_length=1)


class SourceRange(BaseModel):
    record_id: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class Coverage(RecordScope):
    sources: list[SourceRange] = Field(min_length=1, max_length=100)


FILTER = "workspace_id=? AND agent_id=? AND branch_id=? AND scope=?"


def record_in_scope(connection, record_id, scope):
    row = connection.execute(
        f"SELECT * FROM records WHERE id=? AND {FILTER}", (record_id, *scope.values())
    ).fetchone()
    if row is None:
        raise RecordNotFound(record_id)
    return row


def add_relation(connection, source, kind, target, metadata):
    connection.execute(
        "INSERT OR IGNORE INTO relations VALUES (?,?,?,?)",
        (source, kind, target, json.dumps(metadata, ensure_ascii=False)),
    )


def audit(connection, operation, record, actor, details):
    connection.execute(
        "INSERT INTO audit_events(action,record_id,actor,created_at,details_json)"
        " VALUES (?,?,?,datetime('now'),?)",
        (operation, record, actor, json.dumps(details, ensure_ascii=False)),
    )


def operations_for(service):
    store = service.store
    conn = store.conn

    def rebuild_vectors(body: VectorBatch):
        if not service.vector_store or not service.vector_store.index.status.available:
            raise HTTPException(503, "vector index unavailable")
        with store.lock:
            rows = conn.execute(
                f"SELECT id FROM records WHERE {FILTER} AND status IN ('active','candidate')"
                " AND id>? ORDER BY id LIMIT ?", (*body.values(), body.after, body.limit + 1),
            ).fetchall()
        results = []
        for row in rows[:body.limit]:
            with store.lock:
                status = service.retry_vector(row["id"])
            results.append({"record_id": row["id"], "status": status})
        return {"results": results, "next_after": results[-1]["record_id"] if len(rows) > body.limit else None}

    def rebuild_summary(record_id: str, body: SummaryDraft):
        with store.lock:
            source = dict(record_in_scope(conn, record_id, body))
        provider = service.secretary.provider
        if provider is None:
            raise HTTPException(503, "summary provider unavailable")
        key = "summary-rebuild:" + hashlib.sha256(json.dumps([record_id, body.request_id]).encode()).hexdigest()
        with store.lock:
            existing = conn.execute("SELECT * FROM records WHERE idempotency_key=?", (key,)).fetchone()
        if existing is None:
            try:
                result = provider.extract(source["text"])
                summary = result["summary"]
                uncertainty = result.get("uncertainty", "unknown")
                if not isinstance(summary, str) or not summary.strip() or not isinstance(uncertainty, str):
                    raise ValueError("invalid summary response")
            except Exception as error:
                raise HTTPException(502, "summary provider failed") from error
        if existing is not None:
            return dict(existing)
        with store.lock, conn:
            conn.execute("UPDATE records SET status=status WHERE id=?", (record_id,))
            record_in_scope(conn, record_id, body)
            existing = conn.execute("SELECT * FROM records WHERE idempotency_key=?", (key,)).fetchone()
            if existing is not None:
                return dict(existing)
            draft = store._remember(
                commit=False, text=summary, status="candidate", kind="派生摘要", idempotency_key=key,
                workspace_id=body.workspace_id, agent_id=body.agent_id, branch_id=body.branch_id,
                scope=body.scope, source_id=source["source_id"], layer_id=source["layer_id"],
                tags=["derived_summary"],
            )
            add_relation(conn, draft["id"], "covers", record_id, {
                "target_type": "record", "start": 0, "end": len(source["text"]),
                "offset_basis": "record_text",
            })
            audit(conn, "summary_rebuild", draft["id"], body.agent_id, {
                "source_record_id": record_id, "uncertainty": uncertainty, "is_verified": False,
            })
        return draft

    def supersede(record_id: str, body: Revision):
        if record_id == body.replacement_id:
            raise HTTPException(422, "replacement must be a different record")
        with store.lock, conn:
            # Acquire the writer lock before inspecting both records.
            conn.execute("UPDATE records SET status=status WHERE id=? AND " + FILTER,
                         (record_id, *body.values()))
            original = record_in_scope(conn, record_id, body)
            replacement = record_in_scope(conn, body.replacement_id, body)
            if conn.execute(
                "SELECT 1 FROM relations WHERE from_id=? AND relation='supersedes' AND to_id=?",
                (body.replacement_id, record_id),
            ).fetchone() is None:
                if original["status"] != "active" or replacement["status"] != "candidate":
                    raise HTTPException(409, "revision requires an active original and a candidate replacement")
                conn.execute("UPDATE records SET status='active' WHERE id=?", (body.replacement_id,))
                conn.execute("UPDATE records SET status='obsolete',obsolete_reason=? WHERE id=?",
                             (body.reason, record_id))
                add_relation(conn, body.replacement_id, "supersedes", record_id, {"reason": body.reason})
                audit(conn, "supersedes", body.replacement_id, body.agent_id,
                      {"previous_record_id": record_id, "reason": body.reason})
        return {"previous_record_id": record_id, "replacement_id": body.replacement_id}

    def verify(record_id: str, body: Verification):
        if record_id == body.evidence_id:
            raise HTTPException(422, "verification requires separate evidence")
        with store.lock, conn:
            record_in_scope(conn, record_id, body)
            record_in_scope(conn, body.evidence_id, body)
            details = {"evidence_id": body.evidence_id, "conclusion": body.conclusion, "reason": body.reason}
            audit(conn, "verify", record_id, body.verifier, details)
        return details

    def cover(record_id: str, body: Coverage):
        ranges = {}
        with store.lock, conn:
            conn.execute("UPDATE records SET status=status WHERE id=? AND " + FILTER,
                         (record_id, *body.values()))
            summary = record_in_scope(conn, record_id, body)
            if summary["kind"] != "派生摘要":
                raise HTTPException(422, "coverage requires a derived summary")
            for source in body.sources:
                if source.record_id == record_id:
                    raise HTTPException(422, "a summary cannot cover itself")
                original = record_in_scope(conn, source.record_id, body)
                if not source.start < source.end <= len(original["text"]):
                    raise HTTPException(422, "coverage range is outside source text")
                ranges.setdefault(source.record_id, set()).add((source.start, source.end))
            for target_id, spans in ranges.items():
                previous = conn.execute(
                    "SELECT metadata_json FROM relations WHERE from_id=? AND relation='covers' AND to_id=?",
                    (record_id, target_id),
                ).fetchone()
                if previous is not None:
                    metadata = json.loads(previous["metadata_json"])
                    if metadata.get("target_type") != "record" or metadata.get("offset_basis") != "record_text":
                        raise HTTPException(409, "incompatible existing coverage")
                    old_ranges = metadata["ranges"] if "ranges" in metadata else [metadata]
                    spans.update((span["start"], span["end"]) for span in old_ranges)
                metadata = {"target_type": "record", "offset_basis": "record_text",
                            "ranges": [{"start": start, "end": end} for start, end in sorted(spans)]}
                conn.execute(
                    "INSERT INTO relations VALUES (?,'covers',?,?) ON CONFLICT(from_id,relation,to_id)"
                    " DO UPDATE SET metadata_json=excluded.metadata_json",
                    (record_id, target_id, json.dumps(metadata)),
                )
        return {"record_id": record_id, "source_count": len(ranges)}

    def provenance(record_id: str, workspace_id: str = Query(min_length=1),
                   agent_id: str = Query(min_length=1), branch_id: str = Query(min_length=1),
                   scope: Literal["personal", "workspace", "garden"] = "personal",
                   limit: int = Query(50, ge=1, le=200)):
        identity = RecordScope(workspace_id=workspace_id, agent_id=agent_id, branch_id=branch_id, scope=scope)
        with store.lock:
            record_in_scope(conn, record_id, identity)
            relations = conn.execute(
                "SELECT from_id,relation,to_id,metadata_json FROM relations WHERE from_id=?"
                " OR (to_id=? AND relation='supersedes') ORDER BY relation,from_id,to_id LIMIT ?",
                (record_id, record_id, limit),
            ).fetchall()
            events = conn.execute(
                "SELECT action,actor,created_at,details_json FROM audit_events WHERE record_id=?"
                " AND action IN ('verify','summary_rebuild') ORDER BY id DESC LIMIT ?",
                (record_id, limit),
            ).fetchall()
        return {
            "relations": [{"from_id": r["from_id"], "type": r["relation"], "to_id": r["to_id"],
                           "metadata": json.loads(r["metadata_json"])} for r in relations],
            "events": [{"action": r["action"], "actor": r["actor"], "created_at": r["created_at"],
                        "details": json.loads(r["details_json"])} for r in events],
        }

    return {
        "rebuild_vectors": rebuild_vectors, "rebuild_summary": rebuild_summary,
        "supersede": supersede, "verify_memory": verify, "cover_memory": cover,
        "memory_provenance": provenance,
    }


def router_for(service):
    router = APIRouter(prefix="/memory-maintenance")
    operations = operations_for(service)
    for path, method, operation in (
        ("/vectors", "POST", "rebuild_vectors"),
        ("/{record_id}/summary-drafts", "POST", "rebuild_summary"),
        ("/{record_id}/supersede", "POST", "supersede"),
        ("/{record_id}/verify", "POST", "verify_memory"),
        ("/{record_id}/covers", "POST", "cover_memory"),
        ("/{record_id}", "GET", "memory_provenance"),
    ):
        router.add_api_route(path, operations[operation], methods=[method])
    return router
