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
from wiki_synth.generation import run
from wiki_synth.posts import END_MESSAGE, extract_posts
from wiki_synth.results import make_result
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
                              "seq": i+1, "diff_base": "dse~Test@1" if i else None,
                              "body": body, "body_sha256": digest(body.encode()), "body_encoding": "ascii"})
        self.source.write_text("".join(json.dumps(x) + "\n" for x in self.rows))
        self.corpus = self.root / "corpus"
        import_corpus(self.source, self.corpus, "https://example.org/archive")
        self.config = {"schema_version": 2, "model": "llama-8b", "seed": 42, "samples": 2,
                       "max_tokens": 64, "temperature": 0.8, "top_p": 0.95, "max_output_tokens_total": 128,
                       "max_prompt_bytes": 10000,
                       "examples": [{"revision": "dse~Test@1"}, {"revision": "dse~Test@2"}]}

        self.config_path = self.root / "config.json"
        write_json(self.config_path, self.config)

    def plan(self):
        write_json(self.config_path, self.config)
        return prepare(self.corpus, self.config_path)

    def test_roundtrip_and_deterministic_plan(self):
        self.assertEqual(self.source.read_bytes(), (self.corpus / "revisions.jsonl").read_bytes())
        plan = self.plan()
        self.assertEqual(plan, self.plan())
        expected = "Preserved note.\n<<<END_MESSAGE>>>\n\nAn observed reply.\n<<<END_MESSAGE>>>\n\n"
        self.assertEqual(plan["jobs"][0]["request"]["prompt"], expected)
        self.assertEqual(plan["jobs"][0]["request"]["stop"], [END_MESSAGE])
        self.assertEqual(plan["jobs"][0]["request"]["prompt"], plan["jobs"][1]["request"]["prompt"])
        self.assertNotIn("author", plan["jobs"][0])

    def test_start_markers_and_sample_override(self):
        self.config["start_messages"] = True
        plan = self.plan()
        prompt = plan["jobs"][0]["request"]["prompt"]
        self.assertEqual(prompt.count("<<<START_MESSAGE>>>"), 3)
        self.assertTrue(prompt.endswith("<<<START_MESSAGE>>>\n"))
        self.assertEqual(plan["jobs"][0]["request"]["stop"], [END_MESSAGE])
        expanded = prepare(self.corpus, self.config_path, samples=7)
        self.assertEqual(len(expanded["jobs"]), 7)
        self.assertEqual(expanded["output_token_ceiling"], 7 * 64)
        self.assertEqual([j["request"]["seed"] for j in expanded["jobs"]], list(range(42, 49)))
        with self.assertRaises(ValueError):
            prepare(self.corpus, self.config_path, samples=0)
        self.config["start_messages"] = "true"
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.plan()

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

    def test_budget_and_legacy_config_validation(self):
        self.config["max_output_tokens_total"] = 127
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.plan()
        self.config["schema_version"] = 1
        with self.assertRaisesRegex(ValueError, "version 2"):
            self.plan()

    def test_posts_sorted_and_no_duplicate_page_snapshots(self):
        self.config["examples"].reverse()
        plan = self.plan()
        self.assertEqual([p["text"] for p in plan["posts"]], ["Preserved note.", "An observed reply."])
        self.assertEqual(plan["posts"][1]["start"], len(self.rows[0]["body"]))

    def test_non_append_requires_explicit_span(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["body"] = "Revised old note.\nNew reply."
        with self.assertRaisesRegex(ValueError, "explicit post span"):
            extract_posts(rows, self.config["examples"])
        self.config["examples"][1].update(start=18, end=len(rows[1]["body"]))
        posts = extract_posts(rows, self.config["examples"])
        self.assertEqual(posts[1]["text"], "New reply.")

    def test_invalid_duplicate_and_delimiter_examples(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            extract_posts(self.rows, [self.config["examples"][0]] * 2)
        rows = copy.deepcopy(self.rows)
        rows[1]["body"] += END_MESSAGE
        with self.assertRaisesRegex(ValueError, "delimiter-containing"):
            extract_posts(rows, self.config["examples"])
        with self.assertRaisesRegex(ValueError, "at least two"):
            extract_posts(self.rows, [])
        with self.assertRaisesRegex(ValueError, "Invalid post span"):
            extract_posts(self.rows, [{"revision": "dse~Test@1", "start": -1, "end": 10}, self.config["examples"][1]])

    def test_no_overwrite_resume_and_messages_only(self):
        plan = self.plan()
        out = self.root / "run"
        with patch("wiki_synth.generation.complete", side_effect=AssertionError("network called")):
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
        with patch.dict(os.environ, {"ACS_API_KEY": "test-key"}), patch("wiki_synth.generation.complete", side_effect=[response, ProviderError("interrupted")]):
            with self.assertRaises(ProviderError):
                run(plan, out, "acs")
        self.assertTrue((out / "sample-000001.json").exists())
        self.assertFalse((out / ".running").exists())
        with patch.dict(os.environ, {"ACS_API_KEY": "test-key"}), patch("wiki_synth.generation.complete", return_value=response) as mocked:
            run(plan, out, "acs", resume=True)
            self.assertEqual(mocked.call_count, 1)

    def test_missing_key_does_not_create_run(self):
        out = self.root / "absent"
        with patch.dict(os.environ, {"ACS_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "ACS_API_KEY"):
                run(self.plan(), out, "acs")
        self.assertFalse(out.exists())


class ResultTests(unittest.TestCase):
    def test_termination_classification_without_invented_author(self):
        job = {"id": "test", "source_ids": ["source"], "prompt_sha256": "hash"}
        for finish, stop, expected in [("stop", END_MESSAGE, "delimiter"),
                                        ("length", None, "token_limit"),
                                        ("stop", None, "unconfirmed"),
                                        ("stop", 128001, "unconfirmed")]:
            with self.subTest(finish=finish, stop=stop):
                raw = {"choices": [{"text": "A complete post. -- ChosenByModel", "finish_reason": finish, "stop_reason": stop}]}
                result = make_result(job, raw, "acs")
                self.assertEqual(result["termination"], expected)
                self.assertEqual(result["delimiter_reached"], expected == "delimiter")
                self.assertEqual(result["body"], raw["choices"][0]["text"])
                self.assertNotIn("label", result)
                self.assertNotIn("time", result)


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
