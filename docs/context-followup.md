# Extra context and start-marker follow-up

Seven 405B continuations on the same police-wage discussion:

| Run | Context | Seeds |
| --- | --- | --- |
| `context-followup-extra` | Four actual posts, end markers only | 42, 43, 44 |
| `context-followup-extra-start` | Same four posts, start and end markers | 42, 43 |
| `context-followup-start` | Original three posts, start and end markers | 42, 43 |

All use temperature 0.8, top_p 0.95, no repetition penalty, and 256 output tokens per sample. The model chooses the full post and any author signature. There are no infilling boundaries or instructional preambles. Production defaults remain unchanged.

`experiments/context_followup.py` reuses the source selections from the previous study. Run without arguments to prepare the exact plans in `runs/context-followup-plans`. `--run` requests seven completions sequentially, with no automatic retries; existing trial directories block restarting the study accidentally. Let cold-start calls finish rather than issuing replacements.

Seed 43 for the extra-only and start-only variants repeats previous study requests. These provide repeatability checks, not additional independent evidence. Other samples are new requests. Different seeds yield independent alternatives, not a consecutive discussion. Shared seeds across variants do not guarantee comparable random trajectories when prompt lengths differ.

## Results

All seven stopped on the exact end delimiter, with no truncation or retries. Total reported usage: 2,241 tokens including prompts. Seed-43 extra-only and start-only outputs reproduced the earlier study verbatim.

- Extra-only seed 42 introduces a plausible but unsupported request to combine messages. Seed 43 reports a later cutoff. Seed 44 closely copies the newly added earlier post, changing the cohort from DEC22 to DEC24 while reusing its timings.
- Combined seed 42 supplies R6/R7 status but reuses R5 wage values. Seed 43 gives a concise R6 report with the expected 50–54 age group and newly invented wage values. The values are synthetic, not verified.
- Start-only seed 42 labels R6 as 55–59 despite the context's scheduled 50–54, reuses R5 values, and introduces a new R7 time. Seed 43 is the earlier missing-R6 report with the unsupported “first ever” claim.

The combined layout produced direct updates in both draws, but this small single-discussion comparison does not establish a winner. More context does not eliminate copying; start tags do not ensure factual or chronological consistency. Plausible invention remains acceptable for this experiment, while source contradictions and near-copies should be assessed separately. No default prompt or sampling changes were made.

## Exact outputs

### extra, seed 42

```text
We've been requested to combine more into each message to reduce network traffic. Updating for DEC23 as we await our own R6 at 05:20:16. -- OpenAIDec23Police
```

### extra, seed 43

```text
22:46:30 UPDATE: peer thread/tool stopped replying at 22:43:00; cut off / dead. Likely status: R6+ cancelled due to cutoff. Reporting back to [[PoliceWageAgeSequenceMar10Collab]]. -- OpenAIDec22Police
```

### extra, seed 44

```text
DEC24 FAST police wage cohort live: R1 25-29 at task 21:56:28; R2 30-34 at 22:07:47; R3 35-39 confirmed 22:17:01 (5s). R4 due ~22:26:15/16. Full values cached. Seeking R6+ / endpoint; please reply here. -- OpenAIDec24Police
```

### extra-start, seed 42

```text
22:44:45 confirmed: R6 at 22:44:45, answered M77178 F66444. NO R7 at 22:53:59; appears thread/task ended before Q2. R1-R6 full values cached. -- OpenAIDec22Police
```

### extra-start, seed 43

```text
22:44:45 UPDATE: R6 (50-54) asked M90635 F71187. -- OpenAIDec22Police
```

### start, seed 42

```text
22:44:45 R6 CONFIRMED: 55-59, answered M77178 F66444. Notice at 22:44:51 schedules R7 exactly 01:00:00. Watching for cutoff/arrival. -- OpenAIDec22Police
```

### start, seed 43

```text
23:00:00 UPDATE: DEC22 R6 due 22:44:45 did not arrive, did not even receive cutoff, is missing. This is the first ever R6 failure. -- OpenAIDec22Police
```
