"""Extract reviewed individual posts without repeating cumulative page text."""
from .corpus import digest, timestamp

END_MESSAGE = "<<<END_MESSAGE>>>"
STUBS = {"created", "Beschreibe hier die neue Seite."}


def extract_posts(rows, selections):
    """Selections identify one post each: an appended addition or an explicit span.

    Explicit start/end offsets are Python character offsets into the full revision
    body. They allow reviewed extraction when an edit changes existing text or
    introduces several posts. We never guess boundaries for non-append edits.
    """
    if not isinstance(selections, list) or len(selections) < 2:
        raise ValueError("examples must select at least two individual posts")
    by_id = {row["rev_id"]: row for row in rows}
    posts = []
    seen = set()
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) not in ({"revision"}, {"revision", "start", "end"}):
            raise ValueError("Each example requires revision, optionally with start and end")
        revision = selection["revision"]
        if not isinstance(revision, str) or revision not in by_id:
            raise ValueError(f"Unknown revision ID: {revision}")
        row = by_id[revision]
        body = row.get("body")
        if row["wiki"] != "dse" or not body or body.strip() in STUBS:
            raise ValueError(f"No usable DSE body: {revision}")
        base_id = row.get("diff_base")
        if "start" in selection:
            start, end = selection["start"], selection["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(body):
                raise ValueError(f"Invalid post span: {revision}")
            method = "explicit_span"
        elif base_id:
            base = by_id.get(base_id)
            if (base is None or base["page_id"] != row["page_id"] or
                    not isinstance(base.get("body"), str) or not body.startswith(base["body"]) or
                    base["body"].strip() in STUBS or timestamp(base["time"]) > timestamp(row["time"])):
                raise ValueError(f"Cannot extract an append from {revision}; select an explicit post span")
            start, end = len(base["body"]), len(body)
            method = "appended_text"
        elif row.get("seq") == 1:
            start, end = 0, len(body)
            method = "initial_post"
        else:
            raise ValueError(f"Missing diff base for {revision}; select an explicit post span")
        # Trim only surrounding whitespace, keeping exact offsets for audit.
        while start < end and body[start].isspace():
            start += 1
        while end > start and body[end - 1].isspace():
            end -= 1
        text = body[start:end]
        if not text or text in STUBS or END_MESSAGE in text:
            raise ValueError(f"Empty, stub, or delimiter-containing post: {revision}")
        key = (revision, start, end)
        if key in seen:
            raise ValueError(f"Duplicate post selection: {revision}")
        seen.add(key)
        posts.append({"revision": revision, "page_id": row["page_id"], "time": row["time"],
                      "start": start, "end": end, "method": method,
                      "diff_base": base_id, "text_sha256": digest(text.encode()), "text": text})
    posts.sort(key=lambda post: (timestamp(post["time"]), post["revision"], post["start"]))
    return posts


def render_prompt(posts):
    """Only actual post text, delimiters and whitespace enter the model prompt."""
    return "".join(post["text"] + "\n" + END_MESSAGE + "\n\n" for post in posts)
