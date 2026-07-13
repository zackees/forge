import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import rust_tool_resolver

def test_resolver_rejects_non_https():
    assert rust_tool_resolver._sha(b"x") == hashlib.sha256(b"x").hexdigest()

def test_resolver_requires_exact_digest(monkeypatch):
    catalog = {"releases": [{"version": "1", "platforms": [{"platform": "linux", "urls": ["http://x"], "sha256": "0" * 64}]}]}
    index = {"tools": [{"name": "tool", "descriptor": {"url": "https://descriptor", "sha256": rust_tool_resolver._sha(json.dumps(catalog).encode())}}]}
    values = {"https://index": json.dumps(index).encode(), "https://descriptor": json.dumps(catalog).encode()}
    monkeypatch.setattr(rust_tool_resolver, "_get", lambda url: values[url])
    try:
        rust_tool_resolver.resolve("https://index", "tool", "1", "linux")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP URL must be rejected")
