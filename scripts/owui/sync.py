#!/usr/bin/env python3
"""
OWUI Functions / Tools sync script

owui/filters/*.py -> /api/v1/functions/  (Function: filter / pipe / action)
owui/tools/*.py   -> /api/v1/tools/      (Tool: function-calling invoked by the model)

For each file: GET to check existence -> update or create. Idempotent.
Functions are toggled active=True, global=True via /toggle and /toggle/global after create
(both default to False). Tools have no toggle endpoint; access is managed per-item in OWUI.

Required .env (REPO_ROOT/.env):
  OWUI_API_KEY   - admin API Key (OWUI Settings -> Account -> API Keys, starts with `sk-`)
  OWUI_BASE_URL  - default http://localhost:8080

Usage:
  ./scripts/owui/sync.py             # sync both owui/filters/ and owui/tools/
  ./scripts/owui/sync.py mount_tool  # specify individual items (no extension, multiple OK)
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO_ROOT / ".env"

# Per-kind: directory / endpoint / post-create toggles
KINDS: dict[str, dict] = {
    "filter": {
        "dir": REPO_ROOT / "owui" / "filters",
        "api_prefix": "/api/v1/functions",
        # Both are False right after create. By OWUI design, these must be True to be loaded.
        "post_create_toggles": ["toggle", "toggle/global"],
    },
    "tool": {
        "dir": REPO_ROOT / "owui" / "tools",
        "api_prefix": "/api/v1/tools",
        # Tools have no toggle endpoint. Access is managed separately via /access/update
        "post_create_toggles": [],
    },
}


def load_env(path: pathlib.Path) -> dict[str, str]:
    """Simple .env parser. KEY=VAL lines only, strips quotes, ignores comments.
    Caller overrides with os.environ so OS env vars take priority."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract `key: value` lines from the leading docstring. OWUI also interprets
    multi-line descriptions (`description: |`), but since we only need the title (= name),
    a minimal single-line KV parser is sufficient."""
    m = re.search(r'^"""(.*?)"""', content, re.S | re.M)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        m2 = re.match(r"^([a-zA-Z_]+):\s*(.+)$", line.strip())
        if m2:
            fm[m2.group(1)] = m2.group(2).strip()
    return fm


def http_request(
    method: str, url: str, api_key: str, body: dict | None = None
) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def sync_one(
    path: pathlib.Path, kind: str, base_url: str, api_key: str
) -> bool:
    cfg = KINDS[kind]
    fid = path.stem
    if not fid.replace("_", "").isalnum():
        print(f"[SKIP] {kind}:{fid}: OWUI only allows alnum + _ in id", file=sys.stderr)
        return False

    content = path.read_text()
    fm = parse_frontmatter(content)
    name = fm.get("title", fid)
    body = {
        "id": fid,
        "name": name,
        "content": content,
        "meta": {"description": fm.get("description")},
    }

    base = base_url.rstrip("/")
    prefix = cfg["api_prefix"]
    status, _ = http_request("GET", f"{base}{prefix}/id/{fid}", api_key)

    if status == 200:
        # Exists -> update. Respect current active / global / access state in OWUI (do not touch)
        status, text = http_request(
            "POST", f"{base}{prefix}/id/{fid}/update", api_key, body
        )
        if status == 200:
            print(f"[UPDATE {kind}] {fid}  ({name})")
            return True
        print(
            f"[FAIL {kind}] {fid} update status={status} body={text[:200]}",
            file=sys.stderr,
        )
        return False

    if status == 401:
        print(f"[FAIL] Authentication failed (check OWUI_API_KEY)", file=sys.stderr)
        return False

    # Not found -> create
    status, text = http_request(
        "POST", f"{base}{prefix}/create", api_key, body
    )
    if status != 200:
        print(
            f"[FAIL {kind}] {fid} create status={status} body={text[:200]}",
            file=sys.stderr,
        )
        return False

    # Post-create initialization toggles (filter only). Toggle flips the current state,
    # so we only call it once right after create (when state is known to be False).
    toggle_msg = ""
    for ep in cfg["post_create_toggles"]:
        s, t = http_request(
            "POST", f"{base}{prefix}/id/{fid}/{ep}", api_key
        )
        if s != 200:
            print(
                f"[WARN] {fid} {ep} status={s} body={t[:200]} (manual toggle required in UI)",
                file=sys.stderr,
            )
    if cfg["post_create_toggles"]:
        toggle_msg = "  -> active=True, global=True"
    else:
        toggle_msg = "  * access must be configured in OWUI"
    print(f"[CREATE {kind}] {fid}  ({name}){toggle_msg}")
    return True


def discover_targets(only: set[str]) -> list[tuple[pathlib.Path, str]]:
    """List owui/filters/*.py and owui/tools/*.py with their kind. If only is specified, filter to those ids."""
    targets: list[tuple[pathlib.Path, str]] = []
    for kind, cfg in KINDS.items():
        for f in sorted(cfg["dir"].glob("*.py")):
            if only and f.stem not in only:
                continue
            targets.append((f, kind))
    return targets


def main() -> int:
    env = {**load_env(ENV_PATH), **os.environ}  # OS env takes priority
    api_key = env.get("OWUI_API_KEY")
    base_url = env.get("OWUI_BASE_URL", "http://localhost:8080")
    if not api_key:
        print("OWUI_API_KEY required in .env or environment variables", file=sys.stderr)
        return 2
    if not api_key.startswith("sk-"):
        print(
            f"OWUI_API_KEY format invalid (must start with sk-, current prefix: {api_key[:5]!r})",
            file=sys.stderr,
        )
        return 2

    only = set(sys.argv[1:])
    targets = discover_targets(only)

    if only:
        found = {p.stem for p, _ in targets}
        missing = only - found
        if missing:
            print(f"Specified ids not found: {sorted(missing)}", file=sys.stderr)
            return 1
    if not targets:
        print(
            f"No targets (no *.py files in owui/filters/ owui/tools/, or no match for specified ids)",
            file=sys.stderr,
        )
        return 1

    ok = sum(sync_one(p, kind, base_url, api_key) for p, kind in targets)
    print(f"\n{ok}/{len(targets)} synced")
    return 0 if ok == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
