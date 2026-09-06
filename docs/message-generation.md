# Message generator

This component produces text messages and provenance. Environment assembly belongs to other infrastructure.

## Local setup

Python 3.11 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
wiki-synth fetch
wiki-synth import data/raw/prowiki-revisions.jsonl \
  --out data/corpus/prowiki \
  --source-url https://github.com/JoshuaDavid/WikiAgentSwarmInvestigation/tree/774ea465e2957a5e3581a47a8cdb0f8e2395bea2/agent-logs/prowiki
wiki-synth prepare --out runs/dse-prompts
wiki-synth generate --provider mock --out runs/dse-mock
python -m unittest discover -s tests -v
```

The venv, pinned archive, imported corpus, inspected prompts, and mock run are already present in this workspace. Reuse them or choose fresh output directories; import and prepare deliberately refuse to overwrite. `fetch` reuses only a cache with the expected checksum. Downloads and outputs are gitignored. The committed source lock allows another checkout to retrieve the same archive; upstream availability is still required. No archive license is asserted by this project.

The mock returns conspicuous deterministic placeholders. It tests plumbing, not message realism. `prepare` and mock generation make no network calls. `fetch` downloads only the pinned archive URL; it does not crawl or follow links found inside messages.

## Once access arrives

Export `ACS_API_KEY` in your shell, using `.env.example` as a template. It is not automatically loaded. Then:

```sh
wiki-synth models
wiki-synth generate --provider acs --out runs/dse-first-acs
```

Read `/models` output before selecting a larger model. Edit `model` in a copy of `configs/dse-demo.json`, then pass `--config your-config.json`. The default is three 256-token requests against `llama-8b`. Input tokens also cost budget. The configured output ceiling is not a cap on total billed tokens; it bounds requested output for this run. `max_prompt_bytes` guards prompt size but does not count model tokens. Verify the model's context capacity, reduce examples if necessary, and use a small first run.

The client sends raw prompt text, never chat messages. Successful samples are saved immediately. On an interruption, resolve the reported issue and repeat the same command with `--resume`. Completed samples are skipped; changes to corpus, config, provider, or endpoint reject resume. Timeouts can have ambiguous billing status, so check usage before resubmitting. A process killed without cleanup may leave `.running`; remove it only after confirming no writer is active. There is no automatic retry loop.

## Prompt and sampling semantics

`examples` names preserved DSE revision IDs. `gap.before` and `gap.after` name ordered, adjacent observed revisions of one page. Nonempty bodies are required; metadata-only records and deletion stubs cannot serve as seeds. The importer verifies supplied body checksums using the declared encoding or a hash-verified Latin-1 byte representation (recorded in the manifest), and retains all original fields byte-for-byte.

Each prompt contains quoted source snapshots plus an unfinished synthetic message. With `retrospective: true`, it also includes the following observed snapshot as a constraint. This is ordinary next-token completion with both boundaries in context, **not native fill-in-the-middle**. With `false`, the later snapshot's text is withheld. Examples later than the gap start are rejected in either mode. This reduces one form of future information leakage; it does not establish causal fidelity.

Samples are independent candidates conditioned on the same observed context. They receive different seeds, synthetic author labels, and evenly spaced hypothetical times inside the gap. They do not see earlier generated candidates. A batch is not guaranteed to be mutually consistent. Increase `samples` and `max_output_tokens_total` together for larger batches; keep the first experiment small. To change the page or historical interval, select different revision IDs and prepare the prompts for inspection.

No source page is rewritten. Revision bodies can contain multiple messages; they are supplied as snapshots rather than naively counting each revision as a new post. There is no automatic strategic editor, target-model feedback loop, or environment renderer.

## Output contract

`runs/<name>/messages.jsonl` contains **only generated messages**, one JSON object per sample. It is materialized when the batch completes. Completed per-sample JSON files survive a partial run and can be inspected before resuming.

Fields consumed by downstream tooling:

| Field | Meaning |
| --- | --- |
| `id`, `page_id`, `time`, `label`, `body` | Sample ID (unique within a run), source page association, hypothetical timestamp, synthetic author, generated text |
| `synthetic`, `record_type` | Always `true` and `synthetic_message` |
| `source_ids`, `prompt_sha256`, `body_sha256` | Source revision references and content checksums |
| `provider` | `mock` or `acs` |
| `review_status`, `quality_flags` | Initially `unreviewed`; flags identify mock, empty, or truncated outputs |

IDs are scoped to a run; retain the run directory or assign a downstream dataset ID when combining runs. Empty and truncated results are preserved for review, not silently repaired. Outputs are plain untrusted text; this tool never executes generated content.

`run.json` contains the complete prompts, exact config, source checksum and endpoint, but no API key. Each `sample-*.json` additionally retains the provider response, including model/usage fields when returned. `summary.json` aggregates reported token usage; missing usage is not evidence of free calls. Random seeds and pinned inputs make requests reproducible; backend updates and inference behavior can still change real completions.
