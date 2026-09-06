import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from wiki_synth.corpus import digest, import_corpus, load_corpus, write_json
from wiki_synth.prepare import prepare
from wiki_synth.cli import run
from wiki_synth.provider import complete, ProviderError


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.jsonl"
        self.rows = []
        for i, time in enumerate(["2026-06-17T01:00:00Z", "2026-06-17T02:00:00Z"]):
            body = "Preserved note.\n" + ("An observed reply.\n" if i else "")
            self.rows.append({"rev_id": f"dse~Test@{i+1}", "page_id": "dse/Test", "name": "Test",
                              "wiki": "dse", "time": time, "label": "HistoricalAgent",
                              "body": body, "body_sha256": digest(body.encode()), "body_encoding": "ascii"})
        self.source.write_text("".join(json.dumps(x) + "\n" for x in self.rows))
        self.corpus = self.root / "corpus"
        import_corpus(self.source, self.corpus, "https://example.org/archive")
        self.config = {"schema_version": 1, "model": "llama-8b", "seed": 42, "samples": 2,
                       "max_tokens": 64, "temperature": 0.8, "top_p": 0.95, "max_output_tokens_total": 128,
                       "max_prompt_bytes": 10000, "retrospective": True, "examples": [],
                       "gap": {"before": "dse~Test@1", "after": "dse~Test@2", "description": "Hypothetical gap"}}
        self.config_path = self.root / "config.json"
        write_json(self.config_path, self.config)

    def plan(self):
        write_json(self.config_path, self.config)
        return prepare(self.corpus, self.config_path)

    def test_roundtrip_and_deterministic_plan(self):
        self.assertEqual(self.source.read_bytes(), (self.corpus / "revisions.jsonl").read_bytes())
        plan = self.plan()
        self.assertEqual(plan, self.plan())
        self.assertIn("An observed reply.", plan["jobs"][0]["request"]["prompt"])
        self.assertEqual(plan["jobs"][0]["time"], "2026-06-17T01:20:00+00:00")
        self.config["retrospective"] = False
        self.assertNotIn("An observed reply.", self.plan()["jobs"][0]["request"]["prompt"])

    def test_null_body_is_not_a_seed(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["body"] = None
        self.source.write_text("".join(json.dumps(x) + "\n" for x in rows))
        self.corpus = self.root / "null-corpus"
        import_corpus(self.source, self.corpus, "local-fixture")
        with self.assertRaisesRegex(ValueError, "No usable"):
            self.plan()

    def test_tampered_body_rejected_on_import(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["body"] = "Changed"
        self.source.write_text("".join(json.dumps(x) + "\n" for x in rows))
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            import_corpus(self.source, self.root / "bad", "local")

    def test_archive_latin1_carried_utf8_requires_matching_hash(self):
        raw = "Änderungen".encode("utf-8")
        rows = copy.deepcopy(self.rows)
        rows[0].update(body=raw.decode("latin-1"), body_encoding="utf8", body_sha256=digest(raw))
        self.source.write_text("".join(json.dumps(x) + "\n" for x in rows))
        output = self.root / "encoded"
        manifest = import_corpus(self.source, output, "local")
        self.assertEqual(len(manifest["body_encoding_overrides"]), 1)
        self.assertEqual(self.source.read_bytes(), (output / "revisions.jsonl").read_bytes())

    def test_corpus_mutation_rejected(self):
        with (self.corpus / "revisions.jsonl").open("a") as f:
            f.write("\n")
        with self.assertRaisesRegex(ValueError, "changed since import"):
            self.plan()

    def test_budget_and_interval_validation(self):
        self.config["max_output_tokens_total"] = 127
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.plan()
        self.config["max_output_tokens_total"] = 128
        self.config["gap"]["after"] = "dse~Test@1"
        with self.assertRaisesRegex(ValueError, "ordered revisions"):
            self.plan()

    def test_gap_cannot_cross_an_observed_revision(self):
        middle = dict(self.rows[0], rev_id="dse~Test@middle", time="2026-06-17T01:30:00Z")
        self.source.write_text("".join(json.dumps(x) + "\n" for x in self.rows + [middle]))
        self.corpus = self.root / "with-middle"
        import_corpus(self.source, self.corpus, "local")
        with self.assertRaisesRegex(ValueError, "already lies inside"):
            self.plan()

    def test_future_examples_and_mixed_pages_rejected(self):
        self.config["examples"] = ["dse~Test@2"]
        with self.assertRaisesRegex(ValueError, "must not postdate"):
            self.plan()
        self.config["examples"] = []
        self.rows[1]["page_id"] = "dse/OtherPage"
        self.source.write_text("".join(json.dumps(x) + "\n" for x in self.rows))
        self.corpus = self.root / "mixed"
        import_corpus(self.source, self.corpus, "local")
        with self.assertRaisesRegex(ValueError, "same DSE page"):
            self.plan()

    def test_no_overwrite_resume_and_messages_only(self):
        plan = self.plan()
        out = self.root / "run"
        with patch("wiki_synth.cli.complete", side_effect=AssertionError("network called")):
            run(plan, out, "mock")
            first = (out / "messages.jsonl").read_bytes()
            run(plan, out, "mock", resume=True)
        self.assertEqual(first, (out / "messages.jsonl").read_bytes())
        records = [json.loads(x) for x in first.splitlines()]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(x["synthetic"] and x["provider"] == "mock" for x in records))
        with self.assertRaisesRegex(ValueError, "Run exists"):
            run(plan, out, "mock")
        plan["config"]["seed"] += 1
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            run(plan, out, "mock", resume=True)

    def test_partial_run_retains_completed_samples(self):
        plan = self.plan()
        out = self.root / "partial"
        response = {"choices": [{"text": "One note", "finish_reason": "stop"}]}
        with patch.dict(os.environ, {"ACS_API_KEY": "test-key"}), patch("wiki_synth.cli.complete", side_effect=[response, ProviderError("interrupted")]):
            with self.assertRaises(ProviderError):
                run(plan, out, "acs")
        self.assertTrue((out / "sample-000001.json").exists())
        self.assertFalse((out / ".running").exists())
        with patch.dict(os.environ, {"ACS_API_KEY": "test-key"}), patch("wiki_synth.cli.complete", return_value=response) as mocked:
            run(plan, out, "acs", resume=True)
            self.assertEqual(mocked.call_count, 1)

    def test_missing_key_does_not_create_run(self):
        out = self.root / "absent"
        with patch.dict(os.environ, {"ACS_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "ACS_API_KEY"):
                run(self.plan(), out, "acs")
        self.assertFalse(out.exists())


class ProviderTests(unittest.TestCase):
    def invoke(self, handler):
        with patch.dict(os.environ, {"ACS_API_KEY": "test-key", "ACS_API_BASE": "https://infra.acsresearch.org/v1"}):
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                return complete({"model": "llama-8b", "prompt": "Raw prefill", "max_tokens": 12}, client)

    def test_raw_completion_contract(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/completions")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            self.assertEqual(request.headers["x-acs-workload"], "batch")
            payload = json.loads(request.content)
            self.assertEqual(payload["prompt"], "Raw prefill")
            self.assertNotIn("messages", payload)
            return httpx.Response(200, json={"choices": [{"text": " continued", "finish_reason": "stop"}]})
        self.assertEqual(self.invoke(handler)["choices"][0]["text"], " continued")

    def test_200_error_budget_and_malformed_responses(self):
        for status, payload in [(200, {"error": {"code": "modal_cold_boot"}}),
                                (429, {"error": {"code": "budget_exceeded"}}),
                                (200, {"choices": []}), (200, ["unexpected"])]:
            with self.subTest(status=status, payload=payload), self.assertRaises(ProviderError):
                self.invoke(lambda r: httpx.Response(status, json=payload))


if __name__ == "__main__":
    unittest.main()
