import unittest

from helpers import TERMS, result, trial

import tunelib as T


class Basics(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(T.slug_of("/blog/My%20Post/"), "My_Post")
        self.assertEqual(T.slug_of("/"), "home")
        self.assertEqual(T.slug_of("/a/b?x=1"), "b")

    def test_threshold_matches_server_formula(self):
        self.assertAlmostEqual(T.threshold(0.194, 3, 3), 0.194 * (2 / 3) ** 0.5)
        self.assertAlmostEqual(T.threshold(0.194, 1, 1), 0.194 * 2 ** 0.5)

    def test_fidelity_and_coverage(self):
        r = result(meta=3.0, page=6.0)
        self.assertAlmostEqual(T.fidelity(r), 0.5)
        self.assertEqual(len(T.covered(r, TERMS)), 6)
        self.assertEqual(T.uncovered(r, TERMS), TERMS[6:])
        self.assertIsNone(T.fidelity({"error": "x"}))

    def test_terms_for_puts_expected_first_and_caps(self):
        vocab = [f"v{i}" for i in range(200)] + ["term 0"]
        out = T.terms_for(TERMS, vocab)
        self.assertEqual(out[:10], TERMS)
        self.assertEqual(len(out), 100)
        self.assertEqual(len(set(out)), 100)


class Keywords(unittest.TestCase):
    def doc(self, n=10, sources=("https://a.example/x", "www.b.example/y")):
        return {"intent": "How do I X?", "selected": [{"term": f"k{i}", "sources": list(sources)} for i in range(n)]}

    def test_domain_of(self):
        self.assertEqual(T.domain_of("https://www.Example.com/a"), "example.com")
        self.assertEqual(T.domain_of("docs.example.com/path title words"), "docs.example.com")
        self.assertEqual(T.domain_of(""), "")

    def test_valid(self):
        self.assertEqual(T.validate_keywords(self.doc(), "How do I X?"), [])

    def test_wrong_count_intent_and_sources(self):
        p = T.validate_keywords(self.doc(n=9, sources=("a.example/1", "https://a.example/2")), "Other?")
        self.assertTrue(any("intent" in x for x in p))
        self.assertTrue(any("9 keywords" in x for x in p))
        self.assertTrue(any("1 independent source" in x for x in p))

    def test_duplicates(self):
        d = self.doc()
        d["selected"][1]["term"] = "K0"
        self.assertTrue(any("duplicate" in x for x in T.validate_keywords(d, "How do I X?")))


class Trials(unittest.TestCase):
    def test_meta_revision_swaps_everywhere_and_keeps_suffix(self):
        meta = result()["text"]["meta"]
        rev = T.meta_revision(meta, "New title", "New description")
        self.assertEqual(rev["title"], "New title | Example")
        self.assertEqual(rev["ogDescription"], "New description")
        self.assertEqual(rev["jsonLd"], ["Article", "New title", "New description"])

    def test_winner_rules(self):
        self.assertTrue(T.is_winner(trial("up", "level")))
        self.assertTrue(T.is_winner(trial("up", "up")))
        self.assertFalse(T.is_winner(trial("up", "down")))
        self.assertFalse(T.is_winner(trial("level", "up")))
        self.assertFalse(T.is_winner(trial("up", "level", comparable=False)))
        self.assertFalse(T.is_winner({"error": "boom"}))

    def test_best_winner_takes_largest_meta_gain(self):
        a, b, c = {"id": "a"}, {"id": "b"}, {"id": "c"}
        best = T.best_winner([(a, trial(meta_delta=0.3)), (b, trial(meta_delta=0.9)), (c, trial("level"))])
        self.assertIs(best[0], b)
        self.assertIsNone(T.best_winner([(c, trial("level"))]))

    def test_trial_summary_is_small(self):
        s = T.trial_summary(trial())
        self.assertEqual(set(s), {"comparison", "changed", "revisedMeta"})


class Stopping(unittest.TestCase):
    def page(self, trials_per_pass, live="l.json"):
        passes = [{"id": "pass-00", "live": live, "trials": []}]
        for i, wins in enumerate(trials_per_pass, 1):
            passes.append({"id": T.pass_id(i), "live": None, "trials": [{"winner": w} for w in wins]})
        return {"slug": "p", "passes": passes}

    def test_get_pass_creates_and_sorts(self):
        pg = {"passes": []}
        T.get_pass(pg, 2)
        T.get_pass(pg, 0)
        self.assertEqual([p["id"] for p in pg["passes"]], ["pass-00", "pass-02"])
        self.assertEqual(pg["passes"][0]["label"], "Baseline")
        self.assertIs(T.get_pass(pg, 2), pg["passes"][1])

    def test_page_done_on_fidelity(self):
        self.assertIsNotNone(T.page_done(self.page([]), {"l.json": result(meta=6.9, page=7.0)}))
        self.assertIsNone(T.page_done(self.page([]), {"l.json": result(meta=3.0, page=7.0)}))

    def test_page_done_on_patience(self):
        res = {"l.json": result()}
        self.assertIsNone(T.page_done(self.page([[True], [False]]), res))
        self.assertIsNotNone(T.page_done(self.page([[True], [False], [False]]), res))

    def test_stop_reason(self):
        res = {"l.json": result()}
        state = {"maxPasses": 20, "pages": [self.page([[False], [False]])]}
        self.assertIn("noise", T.stop_reason(state, res))
        state = {"maxPasses": 2, "pages": [self.page([[True], [True]])]}
        self.assertIn("2 passes", T.stop_reason(state, res))
        state = {"maxPasses": 20, "pages": [self.page([[True]])]}
        self.assertIsNone(T.stop_reason(state, res))


if __name__ == "__main__":
    unittest.main()
