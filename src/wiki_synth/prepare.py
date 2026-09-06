"""Prepare plain-text post continuations and their external provenance."""
import json
from pathlib import Path
from .corpus import digest, load_corpus
from .posts import END_MESSAGE, extract_posts, render_prompt


def integer(config, name, minimum, maximum):
    value = config[name]
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def prepare(corpus, config_path, samples=None):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    allowed = {"schema_version", "model", "seed", "samples", "max_tokens", "temperature", "top_p",
               "max_output_tokens_total", "max_prompt_bytes", "examples"}
    if not allowed <= set(config) or set(config) - allowed - {"start_messages"} or config["schema_version"] != 2:
        raise ValueError("Config fields must match the version 2 example exactly; gap/retrospective configs are no longer supported")
    if type(config.get("start_messages", False)) is not bool:
        raise ValueError("start_messages must be a boolean")
    if samples is not None:
        integer({"samples": samples}, "samples", 1, 10000)
        config["samples"] = samples
        config["max_output_tokens_total"] = samples * integer(config, "max_tokens", 1, 32000)
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
    rows, manifest = load_corpus(corpus)
    posts = extract_posts(rows, config["examples"])
    prompt = render_prompt(posts, start_messages=config.get("start_messages", False))
    if len(prompt.encode()) > config["max_prompt_bytes"]:
        raise ValueError("Prompt exceeds max_prompt_bytes; select fewer/shorter posts")
    source_ids = list(dict.fromkeys(post["revision"] for post in posts))
    jobs = []
    for i in range(n):
        request = {"model": config["model"], "prompt": prompt, "max_tokens": max_tokens,
                   "temperature": config["temperature"], "top_p": config["top_p"],
                   "seed": config["seed"] + i, "stop": [END_MESSAGE],
                   "n": 1, "stream": False, "echo": False}
        jobs.append({"id": f"sample-{i + 1:06d}", "request": request,
                     "source_ids": source_ids, "prompt_sha256": digest(prompt.encode())})
    return {"schema_version": 2, "config": config, "corpus": manifest, "jobs": jobs,
            "posts": posts, "output_token_ceiling": n * max_tokens,
            "note": "Prompt bytes are a size guard, not a tokenizer count. Input tokens also consume ACS budget."}
