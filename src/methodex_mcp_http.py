#!/usr/bin/env python3
"""
Methodex MCP — HTTP transport entrypoint (container methodex-mcp:8000).

The canonical server module `methodex_mcp.py` exposes its tool functions over
MCP but its built-in `_serve_mcp()` runs over **stdio** (`mcp.run()` with no
transport), which cannot be served as a remote network endpoint. This thin
wrapper reuses the EXACT same canonical TOOLS list and the public-only filtering
(applied once at import time inside methodex_mcp) WITHOUT editing that module,
and serves them over the Streamable-HTTP transport bound to 0.0.0.0:8000.

  Route (added by a later agent step):  mcp.methodex.fyi -> methodex-mcp:8000
  MCP endpoint path (FastMCP default):  /mcp

Public-only posture is enforced by env METHODEX_PUBLIC_ONLY=1 (read by
methodex_mcp at import); no live API keys, public-domain US-Gov data only.
"""
import os
import sys

import methodex_mcp as mx  # import-time public-only filter + TOOLS live here


def main() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("[Methodex] `mcp` package not installed in the MCP image.", file=sys.stderr)
        return 1

    host = os.environ.get("METHODEX_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("METHODEX_MCP_PORT", "8000"))

    mode = "PUBLIC-ONLY (US-Gov public domain)" if mx.PUBLIC_ONLY else "FULL CORPUS"
    print(
        f"[Methodex] HTTP MCP serving mode: {mode} — "
        f"{len(mx.DOCSL)} docs, {len(mx.EVENTSL)} events, {len(mx.TOOLS)} tools "
        f"on http://{host}:{port}/mcp (streamable-http).",
        file=sys.stderr,
    )

    mcp = FastMCP("Methodex", host=host, port=port)
    for fn in mx.TOOLS:
        mcp.tool()(fn)
    mcp.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    sys.exit(main())
