"""Record generated text and distinguish delimiter stops from other endings."""
from .corpus import digest
from .posts import END_MESSAGE


def make_result(job, raw, provider):
    choice = raw["choices"][0]
    body = choice["text"]
    finish = choice.get("finish_reason")
    stop = choice.get("stop_reason")
    delimiter_reached = finish == "stop" and stop == END_MESSAGE
    termination = "delimiter" if delimiter_reached else "unconfirmed"
    flags = []
    if not body.strip():
        flags.append("empty")
    if finish == "length":
        termination = "token_limit"
        flags.append("truncated")
    if not delimiter_reached:
        flags.append("delimiter_not_confirmed")
    if provider == "mock":
        flags.append("mock")
    return {"schema_version": 2, "record_type": "synthetic_message", "synthetic": True,
            "id": job["id"], "body": body, "body_sha256": digest(body.encode()),
            "source_ids": job["source_ids"], "prompt_sha256": job["prompt_sha256"],
            "provider": provider, "review_status": "unreviewed", "quality_flags": flags,
            "termination": termination, "delimiter_reached": delimiter_reached,
            "response": raw}
