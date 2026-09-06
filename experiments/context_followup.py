"""Seven matched-seed 405B trials; prepare by default, --run to call ACS.

Reuses the prior study's reviewed source selections and prompt variants without
changing production defaults. Existing runs prevent accidental duplicate calls.
"""
import argparse
from copy import deepcopy
from pathlib import Path

from prompt_study import plans as previous_plans
from wiki_synth.corpus import digest, write_json
from wiki_synth.generation import run
from wiki_synth.posts import END_MESSAGE


def plans():
    previous = dict(previous_plans())
    variants = []
    for name, source, count in [
        ("extra", "more-context", 3),
        ("extra-start", "more-context", 2),
        ("start", "start-marker", 2),
    ]:
        plan = deepcopy(previous[source])
        template = deepcopy(plan["jobs"][0])
        if name == "extra-start":
            marker = "<<<START_MESSAGE>>>\n"
            template["request"]["prompt"] = "".join(
                marker + post["text"] + "\n" + END_MESSAGE + "\n\n"
                for post in plan["posts"]
            ) + marker
        template["prompt_sha256"] = digest(template["request"]["prompt"].encode())
        plan["jobs"] = []
        for index in range(count):
            job = deepcopy(template)
            job["id"] = f"sample-{index + 1:06d}"
            job["request"]["seed"] = 42 + index
            plan["jobs"].append(job)
        plan["config"].update(samples=count, seed=42, max_output_tokens_total=count * 256)
        plan["output_token_ceiling"] = count * 256
        plan["experiment"] = {
            "name": name, "study": "context-followup",
            "note": "Matched seeds 42/43, plus 44 for extra context. Exact requests are authoritative."
        }
        variants.append((name, plan))
    assert [len(plan["jobs"]) for _, plan in variants] == [3, 2, 2]
    for _, plan in variants:
        for job in plan["jobs"]:
            request = job["request"]
            assert request["model"] == "llama-405b"
            assert request["temperature"] == 0.8 and request["top_p"] == 0.95
            assert request["n"] == 1 and request["max_tokens"] == 256
            assert "repetition_penalty" not in request
    return variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    variants = plans()
    if args.run and any(Path(f"runs/context-followup-{name}").exists() for name, _ in variants):
        parser.error("A trial directory exists; inspect saved results rather than duplicate calls.")
    output = Path("runs/context-followup-plans")
    output.mkdir(exist_ok=True)
    for name, plan in variants:
        write_json(output / f"{name}.json", plan)
        (output / f"{name}.txt").write_text(plan["jobs"][0]["request"]["prompt"], encoding="utf-8")
        if args.run:
            print(run(plan, f"runs/context-followup-{name}", "acs"), flush=True)
        else:
            print(f"Prepared {name}: {len(plan['jobs'])} outputs")


if __name__ == "__main__":
    main()
