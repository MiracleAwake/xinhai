"""Build a new embedding index in a separate copy of a memory database."""

import argparse
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from xinhai.retrieval.embedding import SentenceTransformerProvider
from xinhai.retrieval.sqlite_vec import SQLiteVecIndex
from xinhai.retrieval.vector_store import VectorStore


def require_extension(connection):
    index = SQLiteVecIndex(connection)
    if not index.status.available:
        raise RuntimeError(index.status.reason)


def inspect_database(connection):
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise RuntimeError("SQLite integrity check failed")


def migrate(source, destination, provider):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if not destination.parent.is_dir():
        raise NotADirectoryError(destination.parent)
    if not isinstance(provider.dimensions, int) or provider.dimensions < 1:
        raise ValueError("embedding provider must expose a positive dimension")

    with tempfile.TemporaryDirectory(prefix=".xinhai-vector-", dir=destination.parent) as staging:
        copy = Path(staging) / "memory.sqlite"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, \
                closing(sqlite3.connect(copy)) as target:
            require_extension(original)
            require_extension(target)
            original.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
            inspect_database(target)
            with target:
                target.execute("DROP TABLE IF EXISTS record_vectors")
            vectors = VectorStore(target, provider)
            if not vectors.index.status.available:
                raise RuntimeError(vectors.index.status.reason)
            total = 0
            cursor = target.execute(
                "SELECT id,text FROM records WHERE status IN ('active','candidate') ORDER BY id"
            )
            with closing(cursor):
                for record_id, text in cursor:
                    vectors.add(record_id, text)
                    total += 1
            indexed, = target.execute("SELECT count(*) FROM record_vectors").fetchone()
            if indexed != total:
                raise RuntimeError(f"expected {total} vectors, found {indexed}")
            inspect_database(target)
        # Publish the closed, fully built file without overwriting any destination.
        os.link(copy, destination)
    return {"destination": str(destination), "records_indexed": total, "dimensions": provider.dimensions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--model", required=True, help="local embedding model directory")
    args = parser.parse_args()
    args.source.resolve(strict=True)
    if args.destination.exists():
        parser.error("destination already exists")
    model = Path(args.model).resolve(strict=True)
    if not model.is_dir():
        parser.error("--model must be a local model directory")
    provider = SentenceTransformerProvider(str(model), local_files_only=True)
    print(json.dumps(migrate(args.source, args.destination, provider), ensure_ascii=False))


if __name__ == "__main__":
    main()
