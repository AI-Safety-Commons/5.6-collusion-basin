import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from .corpus import digest, import_corpus, write_json
from .prepare import prepare
from .provider import ProviderError, client_settings, complete, request_json


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


def run(plan, directory, provider, resume=False):
    directory = Path(directory)
    if provider == "acs":
        base, _ = client_settings()  # Fail before creating a run when key is absent.
    else:
        base = None
    identity = {"plan": plan, "provider": provider, "api_base": base}
    if directory.exists():
        if not resume:
            raise ValueError("Run exists; use a new --out or --resume")
        if json.loads((directory / "run.json").read_text())["identity"] != identity:
            raise ValueError("Resume refused: provider, endpoint, corpus or configuration changed")
    else:
        if resume:
            raise ValueError("Cannot resume a run that does not exist")
        directory.mkdir(parents=True)
        write_json(directory / "run.json", {"identity": identity, "created_at": datetime.now(timezone.utc).isoformat()})
    lock_path = directory / ".running"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Run is locked; check for another process before removing .running after a crash") from exc
    os.close(fd)
    try:
        for job in plan["jobs"]:
            target = directory / (job["id"] + ".json")
            if target.exists():
                saved = json.loads(target.read_text())
                if any(saved.get(k) != job[k] for k in ("id", "page_id", "time", "prompt_sha256", "source_ids")):
                    raise ValueError("Saved sample metadata does not match plan")
                if saved.get("body_sha256") != digest(saved["body"].encode()) or saved.get("synthetic") is not True:
                    raise ValueError("Saved sample body changed or synthetic label is missing")
                continue
            print(f"{job['id']}: {provider} completion", file=sys.stderr, flush=True)
            if provider == "mock":
                raw = {"id": "mock-" + job["id"], "model": "offline-placeholder",
                       "choices": [{"text": f"MOCK ONLY: local pipeline check {job['request']['seed']}. No model was called.", "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
            else:
                raw = complete(job["request"])
            body = raw["choices"][0]["text"]
            flags = []
            if not body.strip():
                flags.append("empty")
            if raw["choices"][0].get("finish_reason") == "length":
                flags.append("truncated")
            if provider == "mock":
                flags.append("mock")
            result = {"schema_version": 1, "record_type": "synthetic_message", "synthetic": True,
                      "id": job["id"], "page_id": job["page_id"], "time": job["time"],
                      "label": job["author"], "body": body, "body_sha256": digest(body.encode()),
                      "source_ids": job["source_ids"], "prompt_sha256": job["prompt_sha256"],
                      "provider": provider, "review_status": "unreviewed", "quality_flags": flags,
                      "response": raw}
            temp = target.with_suffix(".tmp")
            write_json(temp, result)
            temp.replace(target)
        records = [json.loads((directory / (j["id"] + ".json")).read_text()) for j in plan["jobs"]]
        message_temp = directory / "messages.jsonl.tmp"
        with message_temp.open("w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps({k: v for k, v in record.items() if k != "response"}, ensure_ascii=False) + "\n")
        message_temp.replace(directory / "messages.jsonl")
        write_json(directory / "summary.json", {"samples": len(records), "provider": provider,
                   "quality_flags": {r["id"]: r["quality_flags"] for r in records},
                   "reported_total_tokens": sum((r["response"].get("usage") or {}).get("total_tokens", 0) for r in records)})
        return {"run": str(directory), "samples": len(records), "provider": provider}
    finally:
        lock_path.unlink(missing_ok=True)


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
    args = parser.parse_args()
    try:
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
