"""Minimal MCP-over-HTTP client for a seo-jev-analyzer deployment. Standard library only.

Configuration comes from the environment, never from files in the repository:
  SEO_JEV_MCP_URL   https://<your deployment>/api/mcp
  SEO_JEV_API_KEY   one of the deployment's MCP_API_KEY values

The key is sent only in the Authorization header. It is never printed, logged or written to disk,
and it is removed from any error text before that text is returned.

  python jevclient.py check            # connectivity and auth, via get_method (no Jev credits)
  python jevclient.py call <tool> <args.json | ->
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PROTOCOL = "2025-06-18"
ENV_URL = "SEO_JEV_MCP_URL"
ENV_KEY = "SEO_JEV_API_KEY"


class ConfigError(RuntimeError):
    pass


def _env(name):
    """Read a variable from the process, then (on Windows) from the user's saved environment,
    so a key set with `setx` works without restarting the shell."""
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                return winreg.QueryValueEx(h, name)[0]
        except OSError:
            return None
    return None


def config():
    url, key = _env(ENV_URL), _env(ENV_KEY)
    missing = [n for n, v in ((ENV_URL, url), (ENV_KEY, key)) if not v]
    if missing:
        raise ConfigError("Set " + " and ".join(missing) + " in your environment (see README).")
    return url, key


def redact(text, key):
    return text.replace(key, "<redacted>") if key and text else text


def parse_body(text):
    """A Streamable HTTP reply is either one JSON object or an SSE stream; return the last message."""
    if not text.strip():
        return None
    if text.lstrip().startswith("{"):
        return json.loads(text)
    msgs = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
    return msgs[-1] if msgs else None


def _post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.headers.get("mcp-session-id"), parse_body(r.read().decode("utf-8"))


def call(tool, args, retries=3, timeout=600, url=None, key=None):
    """Call one tool. Returns its structured result, or {"error": "..."} after the last retry."""
    if url is None or key is None:
        url, key = config()
    last = ""
    for attempt in range(retries):
        try:
            h = {
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
                "authorization": "Bearer " + key,
            }
            sid, _ = _post(url, h, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "seo-tuning-skill", "version": "1"}}}, timeout)
            if sid:
                h["mcp-session-id"] = sid
            h["mcp-protocol-version"] = PROTOCOL
            _post(url, h, {"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout)
            _, res = _post(url, h, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                    "params": {"name": tool, "arguments": args}}, timeout)
            if res is None or "result" not in res:
                raise RuntimeError(json.dumps((res or {}).get("error") or "empty reply")[:500])
            r = res["result"]
            if r.get("isError"):
                raise RuntimeError(r["content"][0]["text"])
            return r.get("structuredContent") or json.loads(r["content"][0]["text"])
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.reason}"
            if e.code in (401, 403):
                break  # a wrong key will not fix itself
        except Exception as e:  # noqa: BLE001 - every failure becomes an {"error"} result
            last = str(e)
        if attempt < retries - 1:
            time.sleep(5 * (attempt + 1))
    return {"error": redact(last, key)}


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if argv[:1] == ["check"]:
            res = call("get_method", {}, retries=1, timeout=60)
            if "error" in res:
                print("FAIL", res["error"])
                return 1
            print("ok  model", res.get("model"), "| noise floor", res.get("noiseFloor"))
            return 0
        if len(argv) == 3 and argv[0] == "call":
            raw = sys.stdin.read() if argv[2] == "-" else open(argv[2], encoding="utf-8").read()
            print(json.dumps(call(argv[1], json.loads(raw)), ensure_ascii=False))
            return 0
    except ConfigError as e:
        print("FAIL", e)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
