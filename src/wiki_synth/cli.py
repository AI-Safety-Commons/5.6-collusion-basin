import argparse
import json
import sys
from pathlib import Path

import httpx
from .corpus import digest, import_corpus, write_json
from .prepare import prepare
from .provider import ProviderError, request_json
from .generation import run


def fetch(lock_path, output):
    lock = json.loads(Path(lock_path).read_text())
    output = Path(output)
    if output.exists():
        if digest(output.read_bytes()) != lock["sha256"]:
            raise ValueError("Existing download does not match source lock")
        return {"cached": str(output), "sha256": lock["sha256"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".part")
    try:
        with httpx.stream("GET", lock["url"], timeout=60, follow_redirects=False) as response:
            response.raise_for_status()
            with temp.open("xb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        if digest(temp.read_bytes()) != lock["sha256"]:
            raise ValueError("Downloaded source checksum does not match lock")
        temp.rename(output)
    finally:
        temp.unlink(missing_ok=True)
    return {"downloaded": str(output), "sha256": lock["sha256"]}


def main():
    parser = argparse.ArgumentParser(description="Local DseWiki synthesis; outputs are always labeled synthetic")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="Download the pinned body archive; no wiki crawl")
    p.add_argument("--lock", default="configs/source.json")
    p.add_argument("--out", default="data/raw/prowiki-revisions.jsonl")
    p = sub.add_parser("import", help="Validate and preserve an archive")
    p.add_argument("source")
    p.add_argument("--out", required=True)
    p.add_argument("--source-url", required=True)
    for name in ("prepare", "generate"):
        p = sub.add_parser(name)
        p.add_argument("--corpus", default="data/corpus/prowiki")
        p.add_argument("--config", default="configs/dse-demo.json")
        p.add_argument("--out", required=True)
        if name == "generate":
            p.add_argument("--provider", choices=["mock", "acs"], default="mock")
            p.add_argument("--resume", action="store_true")
    sub.add_parser("models", help="Read current ACS model IDs/capabilities (requires key)")
    p = sub.add_parser("view", help="Read saved runs in a local browser")
    p.add_argument("--runs", default="runs")
    p.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "view":
            from .viewer import serve
            serve(args.runs, args.port)
            return 0
        if args.command == "fetch":
            result = fetch(args.lock, args.out)
        elif args.command == "import":
            result = import_corpus(args.source, args.out, args.source_url)
        elif args.command == "models":
            result = request_json("GET", "/models")
        else:
            plan = prepare(args.corpus, args.config)
            if args.command == "prepare":
                output = Path(args.out)
                if output.exists():
                    raise ValueError("Output already exists")
                output.mkdir(parents=True)
                write_json(output / "plan.json", plan)
                for job in plan["jobs"]:
                    (output / (job["id"] + ".txt")).write_text(job["request"]["prompt"], encoding="utf-8")
                result = {"prepared": str(output), "samples": len(plan["jobs"]), "output_token_ceiling": plan["output_token_ceiling"]}
            else:
                result = run(plan, args.out, args.provider, args.resume)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ProviderError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
