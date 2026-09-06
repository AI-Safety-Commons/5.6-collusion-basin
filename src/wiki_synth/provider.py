"""ACS raw completions, including errors returned inside HTTP 200 responses."""
import os
from urllib.parse import urlsplit
import httpx


class ProviderError(RuntimeError):
    pass


def client_settings():
    base = os.environ.get("ACS_API_BASE", "https://infra.acsresearch.org/v1").rstrip("/")
    parts = urlsplit(base)
    if (parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"})) or parts.username or parts.password or parts.query or parts.fragment or not parts.hostname:
        raise ValueError("ACS_API_BASE requires HTTPS (or loopback HTTP), without credentials/query/fragment")
    key = os.environ.get("ACS_API_KEY", "").strip()
    if not key:
        raise ValueError("Set ACS_API_KEY to use ACS; use --provider mock without a key")
    return base, key


def request_json(method, endpoint, payload=None, client=None):
    base, key = client_settings()
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(960, connect=30), follow_redirects=False)
    try:
        response = client.request(method, base + endpoint, json=payload,
                                  headers={"Authorization": f"Bearer {key}", "X-Acs-Workload": "batch"})
        try:
            result = response.json()
        except ValueError as exc:
            raise ProviderError(f"ACS returned non-JSON (HTTP {response.status_code})") from exc
        if not isinstance(result, dict):
            raise ProviderError("ACS response must be an object")
        if response.is_error or response.is_redirect or "error" in result:
            error = result.get("error")
            code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
            # Only known codes are displayed; arbitrary server text may echo a prompt or key.
            known = {"invalid_request", "context_length_exceeded", "invalid_api_key", "model_not_found",
                     "budget_exceeded", "queue_full", "rate_limited", "modal_cold_boot", "circuit_open",
                     "upstream_unreachable", "vllm_oom", "vllm_engine_dead", "upstream_server_error"}
            code = code if code in known else "unknown"
            raise ProviderError(f"ACS request failed: HTTP {response.status_code}, {code}. No automatic retry; resume after resolving it.")
        return result
    except httpx.HTTPError as exc:
        # Retrying an ambiguous timeout could create a second billed completion.
        raise ProviderError("ACS transport failed; completion status unknown. Check account usage before resuming.") from exc
    finally:
        if owned:
            client.close()


def complete(payload, client=None):
    result = request_json("POST", "/completions", payload, client)
    choices = result.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ProviderError("Expected exactly one completion choice")
    if not isinstance(choices[0].get("text"), str):
        raise ProviderError("Completion choice is missing text")
    return result
