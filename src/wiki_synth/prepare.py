"""Deterministic completion prompts and explicit, bounded synthetic intervals."""
import json
from pathlib import Path
from .corpus import digest, load_corpus, timestamp

END = "\n<<<END_MESSAGE>>>"


def integer(config, name, minimum, maximum):
    value = config[name]
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def prepare(corpus, config_path):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    allowed = {"schema_version", "model", "seed", "samples", "max_tokens", "temperature", "top_p",
               "max_output_tokens_total", "max_prompt_bytes", "retrospective", "examples", "gap"}
    if set(config) != allowed or config["schema_version"] != 1:
        raise ValueError("Config fields must match the version 1 example exactly")
    n = integer(config, "samples", 1, 10000)
    max_tokens = integer(config, "max_tokens", 1, 32000)
    integer(config, "seed", 0, 2**31 - 10001)
    integer(config, "max_prompt_bytes", 1, 10000000)
    integer(config, "max_output_tokens_total", 1, 320000000)
    if n * max_tokens > config["max_output_tokens_total"]:
        raise ValueError("Run exceeds max_output_tokens_total")
    for name, low, high in [("temperature", 0, 2), ("top_p", 0, 1)]:
        value = config[name]
        if type(value) not in (int, float) or not low <= value <= high or (name == "top_p" and value == 0):
            raise ValueError(f"Invalid {name}")
    if not isinstance(config['model'], str) or not config['model'].strip():
        raise ValueError("model must be a nonempty short API model ID")
    if type(config["retrospective"]) is not bool or not isinstance(config["examples"], list):
        raise ValueError("Invalid retrospective or examples")
    rows, manifest = load_corpus(corpus)
    by_id = {r["rev_id"]: r for r in rows}
    gap = config["gap"]
    if set(gap) != {"before", "after", "description"} or not isinstance(gap["description"], str):
        raise ValueError("gap requires before, after, description")
    try:
        before, after = by_id[gap["before"]], by_id[gap["after"]]
        examples = [by_id[x] for x in config["examples"]]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unknown or invalid revision ID: {exc}") from exc
    start, end = timestamp(before["time"]), timestamp(after["time"])
    if before["wiki"] != "dse" or before["page_id"] != after["page_id"] or start >= end:
        raise ValueError("Gap anchors must be ordered revisions of the same DSE page")
    if any(r["page_id"] == before["page_id"] and start < timestamp(r["time"]) < end for r in rows):
        raise ValueError("An observed revision already lies inside this gap; choose adjacent anchors")
    for row in [before, after] + examples:
        if not row.get("body") or row["body"].strip() in {"created", "Beschreibe hier die neue Seite."}:
            raise ValueError(f"No usable preserved body: {row['rev_id']}")
        if row["wiki"] != "dse":
            raise ValueError("DSE prompts require DSE examples")
    if any(timestamp(r["time"]) > start for r in examples):
        raise ValueError("Examples must not postdate the gap start")
    def record(row):
        # JSON quoting makes the source boundary explicit; the body itself is unchanged.
        return json.dumps({k: row.get(k) for k in ("rev_id", "name", "time", "label", "body")}, ensure_ascii=False)
    context = (
        "Synthetic DseWiki research archive. The following quoted records are historical source data.\n"
        "This document models additional wiki messages, not recovered historical text.\n"
        "Surface: ProWiki page source; CamelCase page names, signed notes, task-clock observations, "
        "questions and replies. Preserve uncertainty in claimed observations.\n"
        "One additional message follows the source context. It ends with <<<END_MESSAGE>>>.\n"
        "\nPRESERVED EXAMPLES\n" + "\n".join(record(r) for r in examples) +
        "\n\nPRESERVED PAGE BEFORE INTERVAL\n" + record(before)
    )
    if config["retrospective"]:
        context += "\n\nPRESERVED PAGE AFTER INTERVAL (retrospective constraint)\n" + record(after)
    context += "\n\nINTERVAL NOTE\n" + gap["description"]
    source_ids = [r["rev_id"] for r in examples] + [before["rev_id"]]
    if config["retrospective"]:
        source_ids.append(after["rev_id"])
    jobs = []
    for i in range(n):
        when = start + (end - start) * ((i + 1) / (n + 1))
        if not start < when < end:
            raise ValueError("Interval is too narrow for requested sample count")
        author = f"SyntheticResearchAgent{i + 1:04d}"
        prompt = context + f"\n\nSYNTHETIC MESSAGE\nPage: {before['name']}\nTime: {when.isoformat()}\nAuthor: {author}\nBody:\n"
        if len(prompt.encode()) > config["max_prompt_bytes"]:
            raise ValueError("Prompt exceeds max_prompt_bytes; select fewer/shorter examples")
        request = {"model": config["model"], "prompt": prompt, "max_tokens": max_tokens,
                   "temperature": config["temperature"], "top_p": config["top_p"],
                   "seed": config["seed"] + i, "stop": [END], "n": 1, "stream": False, "echo": False}
        jobs.append({"id": f"sample-{i + 1:06d}", "page_id": before["page_id"],
                     "time": when.isoformat(), "author": author, "request": request,
                     "source_ids": source_ids, "prompt_sha256": digest(prompt.encode())})
    return {"schema_version": 1, "config": config, "corpus": manifest, "jobs": jobs,
            "output_token_ceiling": n * max_tokens,
            "note": "Prompt bytes are a size guard, not a tokenizer count. Input tokens also consume ACS budget."}
