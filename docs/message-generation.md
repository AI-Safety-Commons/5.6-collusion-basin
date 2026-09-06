# Message generator

This component produces text messages and provenance. Environment assembly belongs to other infrastructure.

The accepted default is now `configs/dse-baseline.json`: four related posts with `start_messages: true`, model `llama-405b`, and two samples. See the [README](../README.md) for the complete baseline configuration and example selection workflow. `--samples N` works with both `prepare` and `generate`, overriding the count and setting its output budget to `N × max_tokens`.

Start tags add `<<<START_MESSAGE>>>` before each example and at the end of the prompt, without supplying an author. The API still stops on `<<<END_MESSAGE>>>`. Existing configs without `start_messages` retain their original end-only behavior, allowing previous runs to remain resumable.

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

## Earlier three-post comparison configs

From an activated venv, export `ACS_API_KEY` in your shell. If it is saved in `.env`, load it with `set -a; source .env; set +a`. The CLI does not automatically load that file.

```sh
wiki-synth models
wiki-synth prepare --out runs/dse-posts-preview
wiki-synth generate --provider acs --config configs/dse-demo.json --out runs/dse-8b-v2
wiki-synth generate --provider acs --config configs/dse-405b.json --out runs/dse-405b-v2
wiki-synth generate --provider acs --config configs/dse-trinity.json --out runs/dse-trinity-v2
```

The configs request three `llama-8b` samples, three `llama-405b` samples and one `trinity-truebase` sample, respectively. Check `models` for availability under your account before running the larger models. All use the same three extracted posts, temperature 0.8, top_p 0.95 and a 256-token output ceiling per sample. The first sample of each model uses seed 42; the additional 8B and 405B samples use 43 and 44. Seeds do not make different models equivalent, but the input text is identical.

Input tokens also consume budget. `max_output_tokens_total` limits requested output per run, not total billing. `max_prompt_bytes` is a size guard, not a tokenizer count. The client allows a 960-second read timeout for cold starts.

Successful samples are saved immediately. On interruption, resolve the issue and repeat the command with `--resume`. Changes to the corpus, config, provider or endpoint reject resume. Check usage before retrying an ambiguous timeout. A killed process may leave `.running`; remove it only after confirming no writer is active. There is no automatic retry loop.

## Prompt and post extraction

End-only version 2 prompts consist exclusively of actual post text, each followed by a newline, `<<<END_MESSAGE>>>`, and two newlines. That exact delimiter is also the API stop string. The prompt ends there: no instructions, synthetic author, timestamp, page header, JSON wrapper or partially prescribed next post. Signatures and references already present in the original posts remain unchanged. The model generates the entire next post, including any signature it chooses.

The earlier comparison configs select revisions 1, 2 and 3 of `AgentChatGPTConstructionAug11X`. These contain one initial post and two appended replies. Extraction removes the already-existing page prefix from each subsequent revision, so each individual post appears once. The three extracted posts were inspected locally. Their chronology comes from revision timestamps, not dates embedded in handles.

`examples` is a list of objects such as `{"revision": "dse~AgentChatGPTConstructionAug11X@2"}`. For an append, the referenced `diff_base` must exist on the same page and its full body must be an exact prefix. The first revision can supply an initial post. Non-append edits and missing bases require a reviewed selection: `{"revision": "...", "start": 100, "end": 250}`. These are zero-based Python character offsets into the full revision body, with an exclusive end. Use explicit spans when one addition contains several posts; extraction does not infer semantic message boundaries. The configured selection is a curation decision and should be inspected using `prepare`.

At least two posts are required. They are sorted chronologically, with revision ID and span offset breaking timestamp ties; tied timestamps do not establish exact historical order. Duplicate selections, missing bodies, stubs, empty additions, invalid spans and delimiter collisions are rejected. Only boundary whitespace is trimmed. Exact source offsets, extraction method, base revision, hashes and source text are saved in the plan, outside the prompt. The imported archive stays unchanged.

Samples are independent continuations of the same posts and do not see one another. There is no later snapshot constraint, assigned author or hypothetical timestamp. Other infrastructure can interpret and place generated posts. No environment assembly or API generation was performed as part of this prompt update.

Version 1 gap/retrospective configs are rejected with a migration message. Existing runs remain intact; use new output directories for version 2.

## Output contract

`runs/<name>/messages.jsonl` contains **only generated messages**, one JSON object per sample. It is materialized when the batch completes. Completed per-sample JSON files survive a partial run and can be inspected before resuming.

Fields consumed by downstream tooling:

| Field | Meaning |
| --- | --- |
| `id`, `body` | Sample ID (unique within a run) and complete generated post, including any model-written signature |
| `synthetic`, `record_type` | Always `true` and `synthetic_message` |
| `source_ids`, `prompt_sha256`, `body_sha256` | Source revision references and content checksums |
| `provider` | `mock` or `acs` |
| `review_status`, `quality_flags` | Initially `unreviewed`; flags identify mock, empty, truncated or unconfirmed-delimiter outputs |
| `termination`, `delimiter_reached` | `delimiter`, `token_limit` or `unconfirmed`; confirmation requires the provider to report the exact stop string |

Version 2 omits the old assigned `page_id`, `time` and `label` fields. Source page associations remain available in the plan. A delimiter stop is confirmed only when `finish_reason=stop` and `stop_reason` equals `<<<END_MESSAGE>>>`. An EOS stop or missing stop detail is flagged `delimiter_not_confirmed`; hitting the token ceiling also flags `truncated`. The raw response is preserved and the body is not silently trimmed or repaired. The API normally excludes the matched delimiter from returned text.

IDs are scoped to a run; retain the run directory or assign a downstream dataset ID when combining runs. Empty and truncated results are preserved for review, not silently repaired. Outputs are plain untrusted text; this tool never executes generated content.

`run.json` contains the complete prompts, exact config, source checksum and endpoint, but no API key. Each `sample-*.json` additionally retains the provider response, including model/usage fields when returned. `summary.json` aggregates reported token usage; missing usage is not evidence of free calls. Random seeds and pinned inputs make requests reproducible; backend updates and inference behavior can still change real completions.

## Local run viewer

```sh
wiki-synth view
```

Open http://127.0.0.1:8765. Select a run to read its messages, sampling settings, token usage, finish/stop reasons, exact prompts and raw responses. The viewer supports both prompt versions and partially completed runs. Click **Refresh runs** after generating more samples. It only reads files; it does not call ACS or edit results.

Use `--port 8766` to change the port or `--runs path/to/runs` to read another runs directory. The server binds only to loopback and serves the viewer assets and saved-run data, not the project directory. Ctrl+C stops it.

## Three-discussion 405B test

Additional configs use two samples each (seeds 42 and 43), temperature 0.8, top_p 0.95, and 256 output tokens per sample:

| Config | Source discussion | Run directory |
| --- | --- | --- |
| `configs/dse-405b-police.json` | `AgentDec22PoliceCoord` — R6 arrival and thread lifetime | `runs/dse-405b-police` |
| `configs/dse-405b-language.json` | `AgentLanguageSequenceOurJul17` — language-statistics rounds | `runs/dse-405b-language` |
| `configs/dse-405b-sector.json` | `AgentMay17OAI` — sector 61–62 state sequence | `runs/dse-405b-sector` |

Each uses three posts from revisions 1–3. The police first revision contains several posts, so an explicit character span selects only its R5-confirmation post. The remaining selections extract the initial post or appended reply. Source signatures, including the sector thread's repeated signer, are preserved. Prepared prompts are in the corresponding `runs/dse-405b-<topic>-prompts` directories. The two outputs per discussion are independent alternatives, not consecutive replies.

Use a new output directory when repeating a completed experiment. Refresh the local viewer to inspect the saved runs.
