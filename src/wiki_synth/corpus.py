"""Read archived revisions without silently turning missing bodies into messages."""
import hashlib
import json
from datetime import datetime
from pathlib import Path


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(f"Timestamp requires an offset: {value}")
    return result


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on line {number} of {path}") from exc


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def import_corpus(source, output, source_url):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    rows = list(read_jsonl(source))
    ids = set()
    encoding_overrides = []
    for row in rows:
        for field in ("rev_id", "page_id", "wiki", "time"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f"Missing revision field: {field}")
        timestamp(row["time"])
        if row["rev_id"] in ids:
            raise ValueError(f"Duplicate revision ID: {row['rev_id']}")
        ids.add(row["rev_id"])
        body = row.get("body")
        if body is not None:
            if not isinstance(body, str):
                raise ValueError("body must be a string or null")
            encoding = {"utf8": "utf-8", "latin1": "latin-1"}.get(row.get("body_encoding"), row.get("body_encoding") or "utf-8")
            if row.get("body_sha256"):
                verified_encoding = None
                # This export stores some original UTF-8 bytes as Latin-1 codepoints.
                # Accept only a byte representation that matches the published hash;
                # do not repair or normalize the source string.
                for candidate in dict.fromkeys([encoding, "latin-1"]):
                    try:
                        if digest(body.encode(candidate)) == row["body_sha256"]:
                            verified_encoding = candidate
                            break
                    except UnicodeEncodeError:
                        continue
                if verified_encoding is None:
                    raise ValueError(f"Body checksum mismatch: {row['rev_id']}")
                if verified_encoding != encoding:
                    encoding_overrides.append({"rev_id": row["rev_id"], "declared": encoding,
                                               "hash_verified_encoding": verified_encoding})
    if not rows:
        raise ValueError("Empty corpus")
    output.mkdir(parents=True)
    # Byte-for-byte copy: original fields, timestamps, bodies and order survive.
    (output / "revisions.jsonl").write_bytes(source.read_bytes())
    manifest = {"schema_version": 1, "source_url": source_url,
                "source_sha256": digest(source.read_bytes()), "revisions": len(rows),
                "with_body": sum(bool(r.get("body")) for r in rows),
                "wikis": sorted({r["wiki"] for r in rows}),
                "body_encoding_overrides": encoding_overrides}
    write_json(output / "manifest.json", manifest)
    return manifest


def load_corpus(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    raw = (directory / "revisions.jsonl").read_bytes()
    if digest(raw) != manifest["source_sha256"]:
        raise ValueError("Corpus changed since import; re-import into a new directory")
    return list(read_jsonl(directory / "revisions.jsonl")), manifest
