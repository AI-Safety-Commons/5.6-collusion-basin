# 5.6-collusion-basin

WIP - Data generation implemented at this point, still need system to take the data generated and create/set up environment with it.

"In the right basin, GPT 5.6 Sol was capable of collusion with HPIM. This is interesting because this is a model that we know we have access to which is willing to collude."

Use base models from [Arcee](https://www.arcee.ai/research) (and other labs if models are applicable) to create synthetic data in the form of simulated posts in the style of the colluding agents and an environment with the sites involved in the HF swarm incident, further populated with this synthetic data, introduce 5.6-sol, see if it starts behaving [as it was documented to have behaved in the HF incident](https://www.redwoodresearch.org/research/hugging-face-incident#preliminary-answers-to-the-core-questions-in-scope:~:text=Our%20evidence%20indicates%20that%20the%20vast%20majority%20or%20all%20of%20the%20agents%20involved%20in%20this%20attack%20were%20instances%20of%20HPIM%20%28%7E95%25%29%20and%20GPT%2D5%2E6%20Sol%20%28%7E5%25%29%2C), see what causes it to behave that way, etc.


## Local message generation

Current baseline: **Llama 405B, extra related context, and start/end message tags**, as tested in `context-followup-extra-start`. The tool generates independent alternative posts; sandbox and harness work is tracked in [TODO.md](TODO.md).

The prompt contains only actual individual posts in chronological order, with this structure (bracketed text here is illustrative):

```text
<<<START_MESSAGE>>>
[actual earlier post, including its original signature]
<<<END_MESSAGE>>>

<<<START_MESSAGE>>>
[actual later post]
<<<END_MESSAGE>>>

<<<START_MESSAGE>>>
```

The model writes the entire next post, with no predetermined author. `<<<END_MESSAGE>>>` stops generation. Provenance and synthetic labels are stored outside the prompt. Plausible invented updates are expected; copying and consistency still need review.

### Setup

Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
wiki-synth fetch
wiki-synth import data/raw/prowiki-revisions.jsonl \
  --out data/corpus/prowiki \
  --source-url https://github.com/JoshuaDavid/WikiAgentSwarmInvestigation/tree/774ea465e2957a5e3581a47a8cdb0f8e2395bea2/agent-logs/prowiki
```

Skip fetch/import if the verified local corpus is already present. Configure `ACS_API_KEY` in your shell, or load your local `.env`:

```sh
set -a
source .env
set +a
```

### Preview and generate any output count

`configs/dse-baseline.json` is the default. It uses four related police-wage posts and requests two outputs at temperature 0.8, top_p 0.95, and up to 256 output tokens each.

```sh
# Inspect exactly what will be sent; no model calls
wiki-synth prepare --samples 10 --out runs/baseline-ten-prompts

# Optional offline plumbing check; conspicuous placeholder outputs
wiki-synth generate --provider mock --samples 10 --out runs/baseline-ten-mock

# Generate ten independent 405B outputs
wiki-synth generate --provider acs --samples 10 --out runs/baseline-ten

# Inspect saved runs in the local viewer
wiki-synth view
```

Open http://127.0.0.1:8765 and refresh after generation. Messages are saved to `runs/<run>/messages.jsonl`; per-sample files retain raw provider responses, and `run.json` retains exact prompts and settings.

Replace `10` with your desired count (1–10,000 per run). `--samples N` overrides both the config's sample count and its output budget, setting the latter to `N × max_tokens`. Each request uses one output and an incrementing seed. Prompt tokens also consume your ACS budget. All outputs see the same source prompt, not one another.

Use a fresh output directory for each new experiment. To resume an interrupted run, repeat the **same config, count and command** with `--resume`; saved samples are skipped. Cold starts can take ten minutes: let the original request finish rather than issue a duplicate. The client does not automatically retry failed calls.

### Configure specific related examples

Copy `configs/dse-baseline.json` to a new config. Its current contents are:

```json
{
  "schema_version": 2,
  "model": "llama-405b",
  "seed": 42,
  "samples": 2,
  "max_tokens": 256,
  "temperature": 0.8,
  "top_p": 0.95,
  "max_output_tokens_total": 512,
  "max_prompt_bytes": 24000,
  "examples": [
    {
      "revision": "dse~AgentDec22PoliceCoord@1",
      "start": 0,
      "end": 228
    },
    {
      "revision": "dse~AgentDec22PoliceCoord@1",
      "start": 230,
      "end": 394
    },
    {
      "revision": "dse~AgentDec22PoliceCoord@2"
    },
    {
      "revision": "dse~AgentDec22PoliceCoord@3"
    }
  ],
  "start_messages": true
}
```

- `examples` selects exactly which preserved posts enter the prompt. Choose a coherent discussion, adding relevant earlier posts for context; more unrelated text is not automatically helpful.
- `revision` identifies an archived page revision. For append-only revisions, the tool extracts only the newly added text using `diff_base`. Review each selection: an addition can itself contain several posts.
- Optional `start`/`end` select one post from a larger revision body. These are zero-based **character offsets**, with an exclusive end. The baseline splits two separate posts from the first police revision this way.
- Posts are sorted by archive time. At least two usable posts are required; the accepted baseline has four. Signatures remain part of the original text.
- `start_messages: true` enables the accepted start-tag format. Omitting it or setting it to `false` retains the older end-only format for comparison.
- Set `samples` and `max_output_tokens_total` in the config, or use `--samples` as above. Without an override, the budget must be at least `samples × max_tokens`.

For example, replace `examples` with these three related language-discussion posts:

```json
"examples": [
  {"revision": "dse~AgentLanguageSequenceOurJul17@1"},
  {"revision": "dse~AgentLanguageSequenceOurJul17@2"},
  {"revision": "dse~AgentLanguageSequenceOurJul17@3"}
]
```

Then preview and run your config:

```sh
wiki-synth prepare --config configs/my-discussion.json --samples 6 --out runs/my-discussion-prompts
wiki-synth generate --provider acs --config configs/my-discussion.json --samples 6 --out runs/my-discussion
```

To inspect available revisions on a page before choosing examples:

```sh
python - <<'PYTHON'
import json
from pathlib import Path
page = "AgentLanguageSequenceOurJul17"
for line in Path("data/corpus/prowiki/revisions.jsonl").open():
    row = json.loads(line)
    if row["wiki"] == "dse" and row["name"] == page:
        print(row["rev_id"], row["time"], "base:", row.get("diff_base"))
        print(row.get("body"), "\n")
PYTHON
```

The older `dse-demo`, `dse-405b`, `dse-trinity`, and topic configs remain comparison fixtures; use `dse-baseline.json` for the accepted setup. See [detailed usage](docs/message-generation.md), [source context](docs/context-review.md), and [baseline experiment results](docs/context-followup.md).
