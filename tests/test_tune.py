"""The loop end to end with a fake seo-jev: init, keywords, baseline, trials, record, report, status."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import TERMS, result, trial

import tune

INTENT = "How do I set up the widget?"


def fake_call(tool, args, **_):
    if tool == "discover_pages":
        return {"urls": ["https://example.com/guide", "https://example.com/"]}
    if tool == "find_boilerplate":
        return {"lines": ["Cookie notice"]}
    if tool == "score_page":
        return result(meta=3.0, page=7.0)
    if tool == "test_revision":
        up = "Better" in (args["revision"].get("title") or "")
        assert args["baseline"]["schema"] == "seo-jev-analyzer/result@1"
        return trial("up" if up else "level", meta_delta=0.6 if up else 0.05)
    raise AssertionError(tool)


class Loop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name) / "w"
        tune.jev = lambda: fake_call

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tune.main(["--work", str(self.work), *args])
        return code, out.getvalue()

    def test_full_loop(self):
        self.run_cmd("init", "--domain", "example.com")
        self.run_cmd("boilerplate")
        prof = json.loads((self.work / "profile.json").read_text(encoding="utf-8"))
        self.assertEqual(prof["boilerplate"], ["Cookie notice"])
        prof["pages"][0]["intent"] = INTENT
        prof["pages"][1]["included"] = False
        (self.work / "profile.json").write_text(json.dumps(prof), encoding="utf-8")

        code, out = self.run_cmd("keywords")
        self.assertEqual(code, 1)
        self.assertIn("no keywords/guide.json", out)
        doc = {"intent": INTENT, "selected": [{"term": t, "sources": ["a.example/x", "b.example/y"]} for t in TERMS]}
        (self.work / "keywords" / "guide.json").write_text(json.dumps(doc), encoding="utf-8")
        code, out = self.run_cmd("keywords", "--apply")
        self.assertEqual(code, 0, out)

        _, out = self.run_cmd("live", "--pass", "0")
        self.assertIn("guide: meta 3.00", out)
        self.assertIn("fidelity 43%", out)

        cands = self.work / "cands.json"
        cands.write_text(json.dumps([
            {"slug": "guide", "id": "c1", "title": "Better title", "description": "Answers the question"},
            {"slug": "guide", "id": "c2", "title": "Other title", "description": "Meh"}]), encoding="utf-8")
        _, out = self.run_cmd("trials", "--pass", "1", "--candidates", str(cands))
        self.assertIn("winner c1", out)

        dec = self.work / "dec.json"
        dec.write_text(json.dumps({"notes": ["Shipped"], "decisions": [
            {"kind": "metadata", "status": "kept", "title": "Winner c1", "diff": [["Old title", "Better title"]]}],
            "pr": "https://example.com/pr/1"}), encoding="utf-8")
        self.run_cmd("record", "--pass", "1", "--slug", "guide", "--json", str(dec))
        self.run_cmd("backlog", "--slug", "guide", "--term", "term 9", "--why", "not covered")
        _, out = self.run_cmd("report", "--title", "Example tuning")
        self.assertIn("1 pages, 2 pass files", out)

        rep = self.work / "report"
        self.assertTrue((rep / "report.html").exists() and (rep / "calc.js").exists())
        idx = json.loads((rep / "data" / "index.json").read_text(encoding="utf-8"))
        page = idx["pages"][0]
        self.assertEqual(page["keywords"][0]["sources"], 2)
        self.assertEqual(page["backlog"][0]["term"], "term 9")
        p1 = json.loads((rep / "data" / "guide" / "pass-01.json").read_text(encoding="utf-8"))
        self.assertEqual(p1["trials"][0]["label"], "c1: Better title (winner)")
        self.assertIn("comparison", p1["trials"][0]["result"])
        self.assertEqual(p1["decisions"][0]["status"], "kept")
        method = json.loads((rep / "data" / "method.json").read_text(encoding="utf-8"))
        self.assertEqual(method["noiseFloor"], 0.194)

        _, out = self.run_cmd("status")
        self.assertIn("CONTINUE", out)


if __name__ == "__main__":
    unittest.main()
