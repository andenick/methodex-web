#!/usr/bin/env python3
"""Minimal MCP Streamable-HTTP handshake probe for methodex-mcp.

Runs the full client handshake against http://<host>:8000/mcp:
  1. initialize           -> capture Mcp-Session-Id
  2. notifications/initialized
  3. tools/list           -> count + names
  4. tools/call resolve_statistic(query="GDP") -> confirm REAL data

Pure stdlib (urllib). Parses SSE responses. Prints a compact JSON summary.
"""
import json
import sys
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"
PROTO = "2025-06-18"


def post(payload, session=None, want_stream=True):
    data = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=30)
    sid = resp.headers.get("Mcp-Session-Id")
    body = resp.read().decode()
    parsed = _parse(body)
    return parsed, sid, resp.status


def _parse(body):
    body = body.strip()
    if not body:
        return None
    # SSE: lines like "event: message\ndata: {...}"
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            chunk = line[len("data:"):].strip()
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"_raw": body[:300]}


def main():
    out = {"url": URL}
    # 1. initialize
    init, sid, status = post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTO,
            "capabilities": {},
            "clientInfo": {"name": "carson-probe", "version": "1.0"},
        },
    })
    out["init_status"] = status
    out["session_id"] = bool(sid)
    si = (init or {}).get("result", {}).get("serverInfo", {})
    out["server_name"] = si.get("name")
    out["protocol"] = (init or {}).get("result", {}).get("protocolVersion")

    # 2. initialized notification (no response expected)
    try:
        post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
             session=sid)
    except Exception as exc:  # noqa: BLE001
        out["initialized_note"] = f"warn: {exc}"

    # 3. tools/list
    tl, _, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    session=sid)
    tools = (tl or {}).get("result", {}).get("tools", [])
    out["n_tools"] = len(tools)
    out["tool_names"] = sorted(t.get("name") for t in tools)

    # 4. invoke one tool — resolve_statistic should return REAL matches
    call, _, _ = post({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "resolve_statistic", "arguments": {"query": "GDP"}},
    }, session=sid)
    res = (call or {}).get("result", {})
    content = res.get("content", [])
    text = ""
    for c in content:
        if c.get("type") == "text":
            text = c.get("text", "")
            break
    out["tool_call_ok"] = bool(text)
    out["tool_call_sample"] = text[:400]

    # 5. invoke methodex_status to confirm public_only + counts
    st, _, _ = post({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "methodex_status", "arguments": {}},
    }, session=sid)
    stres = (st or {}).get("result", {})
    sttext = ""
    for c in stres.get("content", []):
        if c.get("type") == "text":
            sttext = c.get("text", "")
            break
    out["status_sample"] = sttext[:500]

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
