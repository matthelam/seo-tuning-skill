"""The MCP client against a local fake server: JSON and SSE replies, tool errors, auth failures,
and that the key never appears in returned errors."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import helpers  # noqa: F401 - sets the import path

import jevclient

KEY = "test-key-0123456789abcdef"


class Fake(BaseHTTPRequestHandler):
    mode = "json"

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        if self.headers.get("authorization") != "Bearer " + KEY:
            self.send_response(401)
            self.end_headers()
            return
        if body.get("method") == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if body["method"] == "initialize":
            msg = {"jsonrpc": "2.0", "id": 1, "result": {}}
        elif Fake.mode == "toolerror":
            msg = {"jsonrpc": "2.0", "id": 2, "result": {"isError": True, "content": [{"text": "bad input " + KEY}]}}
        else:
            msg = {"jsonrpc": "2.0", "id": 2, "result": {"structuredContent": {"tool": body["params"]["name"]}}}
        sse = Fake.mode == "sse"
        data = (f"event: message\ndata: {json.dumps(msg)}\n\n" if sse else json.dumps(msg)).encode()
        self.send_response(200)
        self.send_header("content-type", "text/event-stream" if sse else "application/json")
        self.send_header("mcp-session-id", "s1")
        self.end_headers()
        self.wfile.write(data)


class Client(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Fake)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}/api/mcp"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, key=KEY):
        return jevclient.call("get_method", {}, retries=1, timeout=5, url=self.url, key=key)

    def test_json_reply(self):
        Fake.mode = "json"
        self.assertEqual(self.call(), {"tool": "get_method"})

    def test_sse_reply(self):
        Fake.mode = "sse"
        self.assertEqual(self.call(), {"tool": "get_method"})

    def test_tool_error_is_redacted(self):
        Fake.mode = "toolerror"
        res = self.call()
        self.assertIn("bad input", res["error"])
        self.assertNotIn(KEY, res["error"])

    def test_wrong_key(self):
        Fake.mode = "json"
        self.assertIn("401", self.call(key="wrong-key-0123456789")["error"])

    def test_parse_body(self):
        self.assertIsNone(jevclient.parse_body("  "))
        self.assertEqual(jevclient.parse_body('data: {"a": 1}\n\ndata: {"a": 2}\n'), {"a": 2})

    def test_missing_config(self):
        old = jevclient._env
        jevclient._env = lambda name: None
        try:
            with self.assertRaises(jevclient.ConfigError) as e:
                jevclient.config()
            self.assertIn("SEO_JEV_MCP_URL", str(e.exception))
        finally:
            jevclient._env = old


if __name__ == "__main__":
    unittest.main()
