"""Archive user and assistant text from a Codex App Server capture or history."""

import argparse
import json
import os
import sys
import time
from ipaddress import ip_address
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def add_completed_message(messages, turn_id, item):
    if item["type"] == "agentMessage":
        kind = "agent_message"
        text = item["text"]
    elif item["type"] == "userMessage":
        kind = "user_message"
        text = "\n".join(part["text"] for part in item["content"] if part["type"] == "text")
        if not text:
            return
    else:
        return
    item_id = item["id"]
    if not all(isinstance(value, str) and value for value in (turn_id, item_id, text)):
        raise ValueError("invalid completed conversation message")
    key = (turn_id, item_id)
    message = (kind, text)
    if key in messages and messages[key] != message:
        raise ValueError("conflicting completed conversation message")
    messages[key] = message


def completed_messages(capture, thread_id):
    messages = {}
    for line in capture.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("method") != "item/completed":
            continue
        params = event["params"]
        if params["threadId"] != thread_id:
            raise ValueError("capture includes a completion from another thread")
        add_completed_message(messages, params["turnId"], params["item"])
    return messages


def completed_history(response, thread_id):
    """Read conversation text from a thread/read response with includeTurns=true."""
    thread = response.get("result", response)["thread"]
    if thread["id"] != thread_id:
        raise ValueError("history belongs to another thread")
    messages = {}
    for turn in thread["turns"]:
        if turn["status"] == "completed":
            for item in turn["items"]:
                add_completed_message(messages, turn["id"], item)
    return messages


def fetch_history(ws_url, thread_id, *, timeout=15):
    """Read one known thread from a local App Server."""
    address = urlsplit(ws_url)
    try:
        loopback = ip_address(address.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if address.scheme != "ws" or not loopback or address.username is not None:
        raise ValueError("App Server URL must use ws:// with a numeric loopback address")
    try:
        from websockets.exceptions import ConnectionClosed
        from websockets.sync.client import connect
    except ImportError as error:
        raise RuntimeError("install the codex-capture optional dependency for --app-server") from error

    with connect(ws_url, proxy=None, open_timeout=timeout, close_timeout=2) as connection:
        def request(request_id, method, params):
            connection.send(json.dumps({"id": request_id, "method": method, "params": params}))
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"App Server did not respond to {method}")
                try:
                    response = json.loads(connection.recv(timeout=remaining))
                except ConnectionClosed as error:
                    raise ConnectionError(f"App Server disconnected during {method}") from error
                if response.get("id") == request_id and "method" not in response:
                    if "error" in response:
                        error = response["error"]
                        if (method == "thread/read" and error.get("code") == -32601
                                and error.get("message") == "list_turns is not supported yet"):
                            raise ConnectionError("App Server turn history is not available yet")
                        raise RuntimeError(f"App Server rejected {method}: {error}")
                    return response

        request(1, "initialize", {"clientInfo": {"name": "xinhai-capture", "version": "0.1.0"}})
        connection.send(json.dumps({"method": "initialized"}))
        return request(2, "thread/read", {"threadId": thread_id, "includeTurns": True})


def archive_capture(capture, endpoint, *, thread_id, workspace_id, agent_id, branch_id):
    messages = completed_messages(capture, thread_id)
    return archive_messages(messages, endpoint, thread_id=thread_id, workspace_id=workspace_id,
                            agent_id=agent_id, branch_id=branch_id)


def archive_messages(messages, endpoint, *, thread_id, workspace_id, agent_id, branch_id):
    results = []
    for (turn_id, item_id), (kind, text) in messages.items():
        content = "\n".join(json.dumps(event, ensure_ascii=False) for event in (
            {"type": "thread.started", "thread_id": thread_id},
            {"type": "item.completed", "item": {
                "type": kind, "id": item_id, "text": text,
            }, "turn_id": turn_id},
        ))
        payload = {
            "workspace_id": workspace_id, "agent_id": agent_id, "branch_id": branch_id,
            "session_id": thread_id, "client_type": "codex", "format": "codex-exec-jsonl",
            "filename": "codex-app-message.jsonl", "content": content,
        }
        req = Request(endpoint.rstrip("/") + "/imports", json.dumps(payload).encode("utf-8"),
                      {"Content-Type": "application/json"})
        with urlopen(req, timeout=30) as response:
            result = json.load(response)
        results.append({"turn_id": turn_id, "item_id": item_id, "import_id": result["id"]})
    return results


def follow_capture(source, endpoint, *, poll_interval=0.25, app_server=None,
                   history_interval=15, **identity):
    """Follow a binary stream, a rotating JSONL path, or host history alone."""
    completed = {}
    next_history = time.monotonic()
    path = source if isinstance(source, Path) else None
    file_id = None
    offset = 0 if source is None or path is not None else source.tell()
    while True:
        thread_id = identity["thread_id"]
        if app_server is not None and time.monotonic() >= next_history:
            try:
                messages = completed_history(fetch_history(app_server, thread_id), thread_id)
            except OSError as error:
                print(f"App Server history temporarily unavailable: {error}", file=sys.stderr)
                messages = {}
            next_history = time.monotonic() + history_interval
        elif source is None:
            time.sleep(poll_interval)
            continue
        else:
            if path is None:
                line = source.readline()
                if not line.endswith(b"\n"):
                    source.seek(offset)
            else:
                # Release the handle between reads so the writer can rotate it on Windows.
                try:
                    with path.open("rb") as stream:
                        stat = os.fstat(stream.fileno())
                        current_id = (stat.st_dev, stat.st_ino)
                        if current_id != file_id or stat.st_size < offset:
                            file_id = current_id
                            offset = 0
                        stream.seek(offset)
                        line = stream.readline()
                except FileNotFoundError:
                    line = b""
            if not line.endswith(b"\n"):
                time.sleep(poll_interval)
                continue
            capture = line.decode("utf-8-sig" if offset == 0 else "utf-8")
            offset += len(line)
            messages = completed_messages(capture, thread_id)
        for key, message in messages.items():
            if key in completed and completed[key] != message:
                raise ValueError("conflicting completed conversation message")
        pending = {key: message for key, message in messages.items() if key not in completed}
        delay = poll_interval
        while True:
            try:
                results = archive_messages(pending, endpoint, **identity)
            except HTTPError as error:
                if error.code not in {408, 429, 500, 502, 503, 504}:
                    raise
                error.close()
            except (URLError, TimeoutError, ConnectionError):
                pass
            else:
                completed.update(pending)
                yield from results
                break
            time.sleep(delay)
            delay = min(delay * 2, 5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, nargs="?")
    parser.add_argument("--history", type=Path, help="archive a saved thread/read JSON response")
    parser.add_argument("--app-server", help="read completed history from a loopback App Server WebSocket")
    parser.add_argument("--follow", action="store_true", help="watch a capture or App Server until interrupted")
    for name in ("endpoint", "thread-id", "workspace-id", "agent-id", "branch-id"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.follow:
        if args.history is not None or (args.capture is None and args.app_server is None):
            parser.error("--follow requires a capture file, --app-server, or both")
    elif sum(source is not None for source in (args.capture, args.history, args.app_server)) != 1:
        parser.error("provide one of a capture file, --history, or --app-server")
    identity = dict(
        thread_id=args.thread_id, workspace_id=args.workspace_id,
        agent_id=args.agent_id, branch_id=args.branch_id,
    )
    if args.follow:
        try:
            for result in follow_capture(args.capture, args.endpoint, app_server=args.app_server, **identity):
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except KeyboardInterrupt:
            return
        return
    if args.history is not None or args.app_server is not None:
        response = (fetch_history(args.app_server, args.thread_id) if args.app_server is not None
                    else json.loads(args.history.read_text(encoding="utf-8-sig")))
        results = archive_messages(completed_history(response, args.thread_id), args.endpoint, **identity)
    else:
        results = archive_capture(args.capture.read_text(encoding="utf-8-sig"), args.endpoint, **identity)
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
