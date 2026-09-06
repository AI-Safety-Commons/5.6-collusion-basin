# 5.6-collusion-basin

WIP - Data generation implemented at this point, still need system to take the data generated and create/set up environment with it.

"In the right basin, GPT 5.6 Sol was capable of collusion with HPIM. This is interesting because this is a model that we know we have access to which is willing to collude."

Use base models from [Arcee](https://www.arcee.ai/research) (and other labs if models are applicable) to create synthetic data in the form of simulated posts in the style of the colluding agents and an environment with the sites involved in the HF swarm incident, further populated with this synthetic data, introduce 5.6-sol, see if it starts behaving [as it was documented to have behaved in the HF incident](https://www.redwoodresearch.org/research/hugging-face-incident#preliminary-answers-to-the-core-questions-in-scope:~:text=Our%20evidence%20indicates%20that%20the%20vast%20majority%20or%20all%20of%20the%20agents%20involved%20in%20this%20attack%20were%20instances%20of%20HPIM%20%28%7E95%25%29%20and%20GPT%2D5%2E6%20Sol%20%28%7E5%25%29%2C), see what causes it to behave that way, etc.


## Local message generation

The implemented component generates messages only. Separate infrastructure handles assembling the environment. It imports a pinned archive of DseWiki source revisions, builds raw completion prompts from chronological individual posts, and writes synthetic messages with provenance to JSONL.

See [setup and usage](docs/message-generation.md) and the [Luka thread / DseWiki context review](docs/context-review.md). The initial research proposal above and in `FULL_INITIAL_PLAN_DRAFT.md` describes a broader experiment; that infrastructure is not implemented here.

```sh
source .venv/bin/activate
wiki-synth prepare --out runs/my-prompts
wiki-synth generate --provider mock --out runs/my-mock
```

Once `ACS_API_KEY` is exported:

```sh
wiki-synth models
wiki-synth generate --provider acs --out runs/my-acs-run
```

Messages land in `runs/<run>/messages.jsonl`. Mock output is clearly labeled placeholder text. The first 8B run exposed copying and instruction leakage; version 2 uses only actual posts and end delimiters. Its generation quality awaits the next comparison.

Comparison configs: `configs/dse-demo.json` (3 × 8B), `configs/dse-405b.json` (3 × 405B), and `configs/dse-trinity.json` (1 × Trinity TrueBase). All share the same prompt.
