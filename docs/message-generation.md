# Message generation

Generate independent synthetic wiki posts from selected, chronological source posts. The default config, [`dse-baseline.json`](../configs/dse-baseline.json), uses Llama 405B with extra context and `<<<START_MESSAGE>>>` / `<<<END_MESSAGE>>>` boundaries. Source metadata stays outside the prompt; the model supplies the whole new post and any signature.

## Setup and run

For a fresh checkout, follow the [README setup steps](../README.md#setup) to install the tool, download and import the corpus, and export `ACS_API_KEY`. No environment, corpus or generated runs are included in the checkout.

For example, from the repository root with the virtual environment activated:

```sh
# Inspect the prompt without calling a model
wiki-synth prepare --samples 6 --out runs/example-prompts

# Generate six independent alternatives
wiki-synth generate --provider acs --samples 6 --out runs/example

# Read the results in a browser at http://127.0.0.1:8765
wiki-synth view
```

Use `--provider mock` for offline placeholder outputs. Choose a new output directory for each run. The viewer reads saved files; click **Refresh runs** after generation.

## Configure examples and output count

Copy the baseline config and pass `--config configs/my-discussion.json` to both `prepare` and `generate`.

- `examples`: select at least two related posts by `revision` ID. Append-only revisions contribute only their added text. For revisions containing multiple posts or edits, select a reviewed `start`/`end` span: zero-based character offsets into the full body, with an exclusive end. Always inspect the prepared prompt.
- `start_messages`: `true` enables the baseline start markers; `false` or omission reproduces the older end-only format.
- `samples`: number of independent outputs, with seeds incrementing from `seed`. `--samples N` overrides this count (1–10,000) and sets the output budget to `N × max_tokens`.
- `max_tokens`, `temperature`, `top_p`: default to 256, 0.8 and 0.95 in the baseline config. Without a count override, `max_output_tokens_total` must cover `samples × max_tokens`. Input tokens also consume API budget; `max_prompt_bytes` is only a size guard.

See the [README examples](../README.md#configure-specific-related-examples) for a complete config and selecting another discussion. Source selection is explicit: the tool does not automatically find related posts or infer semantic post boundaries.

## Saved results and resuming

| File in the output directory | Contents |
| --- | --- |
| `messages.jsonl` | Generated posts and provenance; written when the batch completes |
| `sample-*.json` | Each saved post plus its raw provider response; available during partial runs |
| `run.json` | Exact prompts, settings, source selections and checksums |
| `summary.json` | Quality flags and reported token usage |

Each message has `id`, `body`, `synthetic`, source IDs, hashes, provider and review/termination fields. IDs are unique within a run. `termination` is `delimiter`, `token_limit` or `unconfirmed`; an ordinary EOS stop does not confirm the requested delimiter. Empty, truncated and unconfirmed results remain available for review.

Resume with the same command, config and sample count plus `--resume`. Completed samples are skipped. Let cold-start requests finish; the client waits up to 960 seconds and does not automatically retry. After an ambiguous timeout, check API usage before resuming. If a process was killed, remove its `.running` lock only after confirming no writer remains active.

Historical comparisons and recorded outputs are in [experiment notes](../experiments/notes/README.md). They describe past tests, not files assumed to exist in a new checkout.
