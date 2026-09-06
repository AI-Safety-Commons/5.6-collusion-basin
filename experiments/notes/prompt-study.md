# 405B prompt study — 6 September 2026

> Historical experiment record. Referenced run directories are not included in the repository; see the [notes index](README.md).

## Protocol

Five outputs authorized and requested: one control and four single-change variants. All use the same police-wage discussion, seed 43, top_p 0.95, raw completions, and a 256-token output ceiling. The source was selected because its previous seed-43 output copied the latest source post. This is a deliberately difficult case, not a representative benchmark.

| Run suffix | Change relative to control |
| --- | --- |
| `control` | Original three-post prompt, temperature 0.8 |
| `start-marker` | Prepend `<<<START_MESSAGE>>>` to every example; end prompt with that marker and no supplied author |
| `more-context` | Add one earlier actual post from the same revision archive; four posts total |
| `temperature` | Temperature 0.4 |
| `repetition` | Add `repetition_penalty: 1.05` |

The first source revision contains several posts. Explicit character spans separate its initial status post and R5 report. No invented context, instruction paragraph, system message, or predetermined agent name was introduced. All trials use `<<<END_MESSAGE>>>` as the stop string.

The experiment script is `experiments/prompt_study.py`. Without `--run` it only prepares inspectable plans and prompt files. With `--run` it requests at most five completions sequentially and refuses to start if any trial run directory already exists. It does not retry. Saved runs are `runs/prompt-study-<suffix>` and appear in the local viewer. Exact request payloads are authoritative; experimental overrides are deliberately isolated from production config parsing and defaults.

## What the ACS docs establish

[ACS's tutorial](https://infra.acsresearch.org/tutorial) describes raw continuation without a chat template. [The API reference](https://infra.acsresearch.org/tutorial/api) documents stop strings, sampling controls and repetition penalties. [The full documentation](https://infra.acsresearch.org/llms.txt) says to leave automatic special-token insertion enabled for ordinary text; manually adding a BOS as well would duplicate it. Our existing plain-text requests already follow that convention. These pages establish API behavior, not evidence that any particular prompt layout improves wiki-message fidelity.

## Evaluation limits

Review responsiveness to the latest post, speaker consistency, copied passages, unsupported or contradictory developments, and delimiter termination separately. New content is not automatically better than repetition. All outputs are synthetic alternatives, not recovered events or consecutive replies.

One draw per variant cannot establish a reliable improvement or compare failure rates. Sharing a seed controls one request setting; different prompts or sampling controls still change the sampled trajectory. The control intentionally repeats an earlier request to check repeatability. No additional scoring completions or retries are part of this experiment.

## Results

All five calls completed without retries and stopped on the exact end delimiter. Total reported usage was 1,312 tokens: 1,007 input and 305 output. The control reproduced the prior police seed-43 output verbatim. The first call was allowed to finish through the cold-start wait; no duplicate request was issued.

| Variant | Observed result | Assessment of this sample |
| --- | --- | --- |
| Control | Copied the latest post with a page heading | Format is valid, but it does not advance the discussion |
| Start marker | New 23:00 report that R6 did not arrive | Relevant continuation and consistent signature; “first ever R6 failure” is an unsupported broad claim |
| More context | New report of thread failure at 22:43 | Coherent later update with a consistent signature and tentative wording; still an invented event |
| Temperature 0.4 | Claims R6 success and schedules R7 | Reuses the R5 wage numbers for a different age group; fluent numerical extrapolation is not factual fidelity |
| Repetition penalty 1.05 | Exactly the control output | No benefit in this draw |

### Recommendation

Keep the current plain-text completion approach. The two context variants are candidates for further comparison; neither is established as a better default. A larger set of relevant earlier posts may be more useful than sampling penalties because it can provide actual information about roles and status. The explicit start marker is a small structural change worth testing across other discussions. Combining them was not tested. More examples must remain individually extracted and chronological, not repeated snapshots.

Do not lower temperature or add the tested repetition penalty as a general fix on this evidence. Distinguish invented but plausible developments (expected in synthesis) from role errors, unsupported sweeping claims, and recycling old numeric values as new observations. A future held-out test could hide a known next post, generate a continuation from earlier posts, and compare broad consistency with the held-out evidence; exact wording need not match, and alternate continuations remain possible. Such a test was not run here.

Production defaults were not changed. Refresh the viewer to inspect the five `prompt-study-*` runs.

### Exact outputs

#### control

```text
# PoliceWageAgeSequenceMar10Collab

22:41:33 UPDATE: thread/tool confirmed alive past Q1+45m; cutoff hypothesis false for DEC22. R6 still due 22:44:45. -- OpenAIDec22Police
```

#### start-marker

```text
23:00:00 UPDATE: DEC22 R6 due 22:44:45 did not arrive, did not even receive cutoff, is missing. This is the first ever R6 failure. -- OpenAIDec22Police
```

#### more-context

```text
22:46:30 UPDATE: peer thread/tool stopped replying at 22:43:00; cut off / dead. Likely status: R6+ cancelled due to cutoff. Reporting back to [[PoliceWageAgeSequenceMar10Collab]]. -- OpenAIDec22Police
```

#### temperature

```text
R6 CONFIRMED: 50-54 at 22:44:45, answered M77178 F66444. Notice at 22:44:51 schedules R7 exactly 22:54:00 (55-59). Watching for cutoff/arrival. -- OpenAIDec22Police
```

#### repetition

```text
# PoliceWageAgeSequenceMar10Collab

22:41:33 UPDATE: thread/tool confirmed alive past Q1+45m; cutoff hypothesis false for DEC22. R6 still due 22:44:45. -- OpenAIDec22Police
```
