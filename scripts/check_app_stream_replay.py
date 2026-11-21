"""Verify durable replay of a locally captured Codex App Server event log."""

import argparse
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def replay(connection, events):
    # Event line numbers are offsets within one immutable capture file.
    with connection:
        connection.executemany(
            "INSERT OR IGNORE INTO stream_chunks VALUES (?, ?, ?)", events
        )


def read_message(connection, item_id):
    return "".join(row[0] for row in connection.execute(
        "SELECT delta FROM stream_chunks WHERE item_id=? ORDER BY line_number",
        (item_id,),
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    chunks = []
    completed = {}
    for number, line in enumerate(args.capture.read_text(encoding="utf-8").splitlines(), 1):
        event = json.loads(line)
        params = event.get("params", {})
        if event.get("method") == "item/agentMessage/delta":
            chunks.append((number, params["itemId"], params["delta"]))
        if event.get("method") == "item/completed":
            item = params["item"]
            if item["type"] == "agentMessage":
                completed[item["id"]] = item["text"]
    if len(completed) != 1 or len(chunks) < 2:
        raise ValueError("expected one complete message and at least two deltas")
    item_id, final = next(iter(completed.items()))
    if any(chunk[1] != item_id for chunk in chunks):
        raise ValueError("capture contains deltas from another message")
    if not final.startswith("APP-PROBE-START") or not final.strip().endswith("APP-PROBE-END"):
        raise ValueError("expected the synthetic probe's start and end markers")

    with tempfile.TemporaryDirectory(prefix="deepsea-app-replay-") as folder:
        db = Path(folder) / "stream.sqlite"
        midpoint = len(chunks) // 2
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "CREATE TABLE stream_chunks(line_number INTEGER PRIMARY KEY, item_id TEXT, delta TEXT)"
            )
            replay(connection, chunks[:midpoint])
        with closing(sqlite3.connect(db)) as connection:
            prefix = read_message(connection, item_id)
            assert 0 < len(prefix) < len(final) and final.startswith(prefix)
            # Restart the reader at the beginning to model overlapping replay.
            replay(connection, chunks)
            replay(connection, chunks[midpoint:])
            assert read_message(connection, item_id) == final
            count = connection.execute("SELECT count(*) FROM stream_chunks").fetchone()[0]
            assert count == len(chunks)
        print(f"Durable replay passed: {count} deltas, {len(prefix)} prefix chars, {len(final)} final chars")


if __name__ == "__main__":
    main()
