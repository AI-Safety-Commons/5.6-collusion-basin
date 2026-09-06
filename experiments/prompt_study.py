"""Five bounded 405B trials. Defaults to preparing plans; --run calls ACS.

Run from the project root. Production configs and prompt rendering are unchanged.
Existing trial output directories are never overwritten or automatically retried.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from wiki_synth.corpus import digest, load_corpus, write_json
from wiki_synth.generation import run
from wiki_synth.posts import END_MESSAGE, extract_posts, render_prompt
from wiki_synth.prepare import prepare


def plans():
    base = prepare("data/corpus/prowiki", "configs/dse-405b-police.json")
    base["jobs"] = [deepcopy(base["jobs"][1])]  # Seed 43: existing copying case.
    base["jobs"][0]["id"] = "sample-000001"
    base["config"].update(samples=1, seed=43, max_output_tokens_total=256)
    base["output_token_ceiling"] = 256
    variants = []
    for name, hypothesis in [
        ("control", "Repeat the original seed-43 request to check the comparison baseline."),
        ("start-marker", "A demonstrated start marker may signal a new post more clearly."),
        ("more-context", "One earlier post may improve tracking of the same discussion."),
        ("temperature", "Lower temperature may improve consistency, but may increase copying."),
        ("repetition", "A mild repetition penalty may reduce copying, but distort repeated names or facts."),
    ]:
        plan = deepcopy(base)
        request = plan["jobs"][0]["request"]
        if name == "start-marker":
            marker = "<<<START_MESSAGE>>>\n"
            request["prompt"] = "".join(marker + p["text"] + "\n" + END_MESSAGE + "\n\n" for p in plan["posts"]) + marker
        elif name == "more-context":
            rows, _ = load_corpus("data/corpus/prowiki")
            revision = "dse~AgentDec22PoliceCoord@1"
            body = next(r["body"] for r in rows if r["rev_id"] == revision)
            earlier = {"revision": revision, "start": 0, "end": body.index("\n\nR5 CONFIRMED:")}
            plan["config"]["examples"].insert(0, earlier)
            plan["posts"] = extract_posts(rows, plan["config"]["examples"])
            request["prompt"] = render_prompt(plan["posts"])
        elif name == "temperature":
            request["temperature"] = 0.4
            plan["config"]["temperature"] = 0.4
        elif name == "repetition":
            request["repetition_penalty"] = 1.05
        plan["experiment"] = {"name": name, "hypothesis": hypothesis,
                              "note": "Exact job request is authoritative; experiment overrides are not production config options."}
        plan["jobs"][0]["prompt_sha256"] = digest(request["prompt"].encode())
        variants.append((name, plan))
    assert len(variants) == 5
    assert all(len(p["jobs"]) == 1 and p["jobs"][0]["request"]["n"] == 1 for _, p in variants)
    return variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make at most five completion calls; no retries")
    args = parser.parse_args()
    variants = plans()
    # Fail before any spending if this experiment has already been started.
    if args.run and any(Path(f"runs/prompt-study-{name}").exists() for name, _ in variants):
        parser.error("A trial run already exists. Inspect it; this script will not repeat calls.")
    prepared = Path("runs/prompt-study-plans")
    prepared.mkdir(exist_ok=True)
    for name, plan in variants:
        write_json(prepared / f"{name}.json", plan)
        (prepared / f"{name}.txt").write_text(plan["jobs"][0]["request"]["prompt"], encoding="utf-8")
        if args.run:
            print(run(plan, f"runs/prompt-study-{name}", "acs"), flush=True)
        else:
            print(f"Prepared {name}: {plan['experiment']['hypothesis']}")


if __name__ == "__main__":
    main()
