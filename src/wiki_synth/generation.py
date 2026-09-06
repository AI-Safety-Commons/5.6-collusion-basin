"""Execute resumable message batches; generation never modifies the corpus."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus import digest, write_json
from .provider import client_settings, complete
from .results import make_result

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
                if any(saved.get(k) != job[k] for k in ("id", "prompt_sha256", "source_ids")):
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
            result = make_result(job, raw, provider)
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

