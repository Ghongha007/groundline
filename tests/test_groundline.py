import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from groundline.checks import check_all, numbers
from groundline.cli import draft_sentences, main
from groundline.llm import second_opinion
from groundline.text import passages_from, split_sentences

EX = Path(__file__).resolve().parent.parent / "examples"
SRC, DRAFT = EX / "audit_report.txt", EX / "ai_summary.md"


def run():
    return check_all(draft_sentences(str(DRAFT)), passages_from([SRC]))


class TestText(unittest.TestCase):
    def test_sentences_keep_abbreviations_and_decimals(self):
        s = split_sentences("Dr. Rao paid Rs. 4.9 million to Halden Ltd. in 2025. It was late. U.S. officials agreed.")
        self.assertEqual(len(s), 3)

    def test_numbers(self):
        vals = [v for v, _, _ in numbers("It spent 11.8 million, 83 per cent, 1,250 trucks and 3 crore")]
        for want in (11.8e6, 83, 1250, 3e7):
            self.assertIn(want, vals)
        self.assertEqual(numbers("a 5 m wall")[0][0], 5)          # metres, not million


class TestChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run()
        cls.by = {r.sentence[:25]: r for r in cls.r}

    def find(self, start):
        return next(r for r in self.r if r.sentence.startswith(start))

    def test_correct_sentences_match(self):
        for start in ("Riverford District Council budgeted", "The audit reviewed 40", "Three contractors", "The council has accepted"):
            self.assertEqual(self.find(start).verdict, "matched", start)

    def test_changed_number(self):
        r = self.find("Of the 212")
        self.assertEqual(r.verdict, "check")
        self.assertTrue(any(f.kind == "number" and "146" in f.text and "164" in f.text for f in r.flags))

    def test_invented_quote(self):
        self.assertTrue(any(f.kind == "quote" for f in self.find("Priya Nandakumar").flags))

    def test_overstated_claim(self):
        r = self.find("This proves")
        self.assertNotEqual(r.verdict, "matched")
        self.assertTrue(any(f.kind == "wording" for f in r.flags))

    def test_unsupported_sentence(self):
        r = self.find("Local residents")
        self.assertEqual(r.verdict, "no match")
        self.assertTrue(any(f.kind == "name" and "Riverford Gazette" in f.text for f in r.flags))

    def test_name_at_sentence_start(self):
        src = passages_from([SRC])
        r = check_all(["Marlow Paving Ltd received 4.9 million from the council."], src)[0]
        self.assertTrue(any(f.kind == "name" and "Marlow Paving" in f.text for f in r.flags))
        r = check_all(["Halden Surfacing Ltd received 4.9 million across 18 contracts."], src)[0]
        self.assertFalse(any(f.kind == "name" for f in r.flags))

    def test_real_quote_passes(self):
        src = passages_from([SRC])
        r = check_all(['Nandakumar said: "We have asked the contractors to repair the failed sections at their own cost."'], src)[0]
        self.assertFalse(any(f.kind == "quote" for f in r.flags))


class Fake(BaseHTTPRequestHandler):
    reply = {}

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({"choices": [{"message": {"content": "Sure:\n" + json.dumps(Fake.reply)}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestLLM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_quote_guard(self):
        r = [x for x in run() if x.sentence.startswith("Of the 212")]
        Fake.reply = {"verdict": "contradicted", "quote": "Of the 212 road sections planned, 164 were completed.", "why": "164, not 146"}
        second_opinion(r, self.base, "fake")
        self.assertTrue(r[0].llm["trusted"]); self.assertEqual(r[0].verdict, "contradicted")

        r = [x for x in run() if x.sentence.startswith("Of the 212")]
        Fake.reply = {"verdict": "contradicted", "quote": "Only 100 sections were completed.", "why": "made up"}
        second_opinion(r, self.base, "fake")
        self.assertFalse(r[0].llm["trusted"]); self.assertEqual(r[0].verdict, "check")


class TestCLI(unittest.TestCase):
    def test_reports(self):
        with tempfile.TemporaryDirectory() as d:
            code = main(["check", "-s", str(SRC), "-d", str(DRAFT), "-o", f"{d}/r.html", "--md", f"{d}/r.md",
                         "--json", f"{d}/r.json", "-q"])
            self.assertEqual(code, 1)                                   # unsupported sentences present
            data = json.loads(Path(f"{d}/r.json").read_text())
            self.assertEqual(len(data["sentences"]), 8)
            h = Path(f"{d}/r.html").read_text()
            self.assertIn("Groundline report", h); self.assertNotIn("</script><script>alert", h)
            md = Path(f"{d}/r.md").read_text()
            self.assertIn("Methodology note (draft)", md)
            self.assertIn("Methodology note (draft)", h)
            # the note must not claim a review the tool cannot know happened
            for text in (md, h):
                self.assertNotIn("was then reviewed", text)
                self.assertIn("should review every flag", text)

    def test_missing_file(self):
        self.assertEqual(main(["check", "-s", "nope.txt", "-d", str(DRAFT), "-q"]), 2)


if __name__ == "__main__":
    unittest.main()
