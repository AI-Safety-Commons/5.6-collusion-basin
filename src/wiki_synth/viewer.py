"""Read-only loopback viewer for saved generation runs."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STATIC = Path(__file__).with_name("static")


def read_object(path):
    if path.is_symlink():
        raise ValueError("Symlinked files are not supported")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def run_directory(root, name):
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Invalid run name")
    directory = root / name
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Unknown run")
    return directory


def load_run(root, name, include_samples=True):
    directory = run_directory(root, name)
    info = read_object(directory / "run.json")
    identity = info["identity"]
    plan = identity["plan"]
    config = plan["config"]
    result = {"name": name, "created_at": info.get("created_at"),
              "provider": identity.get("provider"), "config": config,
              "planned": len(plan["jobs"]), "completed": 0, "samples": [], "errors": []}
    for job in plan["jobs"]:
        sample_id = job["id"]
        if not isinstance(sample_id, str) or Path(sample_id).name != sample_id or sample_id in {".", ".."}:
            raise ValueError("Invalid sample ID")
        path = directory / (sample_id + ".json")
        if not path.exists():
            continue
        try:
            sample = read_object(path)
            result["completed"] += 1
            if include_samples:
                result["samples"].append({"record": sample, "request": job["request"]})
        except (ValueError, OSError) as exc:
            result["errors"].append(f"Cannot read {sample_id}: {type(exc).__name__}")
    if include_samples:
        result["sources"] = {key: plan.get("corpus", {}).get(key) for key in ("source_url", "source_sha256", "revisions")}
    return result


def list_runs(root):
    runs, errors = [], []
    if not root.is_dir():
        return {"runs": [], "errors": ["Runs directory does not exist yet."]}
    for directory in root.iterdir():
        if directory.is_symlink() or not directory.is_dir() or not (directory / "run.json").exists():
            continue
        try:
            runs.append(load_run(root, directory.name, include_samples=False))
        except (ValueError, KeyError, TypeError, OSError):
            errors.append(f"Cannot read run: {directory.name}")
    runs.sort(key=lambda run: (run["provider"] == "acs", run["created_at"] or "", run["name"]), reverse=True)
    return {"runs": runs, "errors": errors}


def make_handler(root):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Keep browser requests tied to loopback; do not serve the workspace.
            if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                self.send_error(403)
                return
            url = urlsplit(self.path)
            try:
                if url.path == "/api/runs":
                    data = list_runs(root)
                elif url.path == "/api/run":
                    name = parse_qs(url.query).get("name", [""])[0]
                    data = load_run(root, name)
                else:
                    assets = {"/": ("viewer.html", "text/html"), "/viewer.js": ("viewer.js", "text/javascript"),
                              "/viewer.css": ("viewer.css", "text/css")}
                    if url.path not in assets:
                        self.send_error(404)
                        return
                    filename, mime = assets[url.path]
                    self.respond((STATIC / filename).read_bytes(), mime)
                    return
                self.respond(json.dumps(data, ensure_ascii=False).encode(), "application/json")
            except (ValueError, KeyError, TypeError, OSError):
                self.respond(b'{"error":"Run unavailable or malformed. Refresh after the current write completes."}', "application/json", 400)

        def respond(self, body, mime, status=200):
            self.send_response(status)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(runs="runs", port=8765):
    root = Path(runs).resolve()
    with ThreadingHTTPServer(("127.0.0.1", port), make_handler(root)) as server:
        print(f"Run viewer: http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Reading {root} • Ctrl+C to stop", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
