# Code Interpreter (Pyodide) Environment

OWUI's Code Interpreter runs Python in **Pyodide in the browser**.
This document is an **engineering reference** for how this environment is
configured in LLENS. For model-facing usage instructions, see
`prompts/code-interpreter.md` (the production system prompt).

## Environment Versions (as of 2026-05-18)

| Item | Value |
|---|---|
| OWUI | v0.9.5 (`ghcr.io/open-webui/open-webui:v0.9.5`) |
| Pyodide | 0.28.0.dev0 |
| Python | 3.13.2 |
| ABI | `cp313-cp313-pyodide_2025_0_wasm32` (emscripten_4_0_9) |

When upgrading OWUI, sync the `FROM` tag in `docker/open-webui/Dockerfile`
and the `image` tag in `docker-compose.yml`, then rebuild with
`docker compose build --pull open-webui`.

## 3 Sources of Available Packages

1. **Python standard library** -- Bundled with the Pyodide runtime. Usable directly via `import`.
2. **OWUI bundle** (`/pyodide/*.whl`) -- A curated set of wheels selected by OWUI.
   Auto-loaded on `import` or fetched via `await micropip.install("name")`.
3. **LLENS pyodide-extra** (`/static/pyodide-extra/*.whl`) -- Additional wheels
   bundled by LLENS via `docker/open-webui/Dockerfile`. Fetched using the
   pyfetch + index.json pattern described in `prompts/code-interpreter.md`.

The actual individual package names are listed in the table in
`prompts/code-interpreter.md` (no duplication is maintained to keep them
in sync with the production prompt passed to the model).

## pyodide-lock.json Pitfall

The `/pyodide/pyodide-lock.json` bundled with OWUI contains **all 340
entries from Pyodide upstream**, but only **46 of them** actually have
wheel files present. The remaining 294 entries will **fail with 404**
when you run `await micropip.install("...")`.

This is why `lxml` / `markupsafe` / `pycryptodome` had to be added on
the LLENS side (pyodide-extra) via Route B. Before adding new packages,
first verify whether they actually exist in the OWUI bundle using
`make list-pyodide-bundle` or similar.

## Adding to pyodide-extra

There are 2 routes in `docker/open-webui/Dockerfile`:

- **Route A** (`pip download --platform=any --python-version=3.12`)
  For packages that have a `py3-none-any` pure-Python wheel on PyPI. Fetched from PyPI at build time.
- **Route B** (jsdelivr `v0.28.0/full` via `curl`)
  For packages requiring C extensions with a Pyodide-specific emscripten build (not available on PyPI).
  Directly downloaded with matching ABI `cp313-cp313-pyodide_2025_0_wasm32`.

`index.json` is auto-generated at build time (PEP 503 normalized name -> wheel filename map).
The model only needs to list package names in a tuple; no wheel filename hallucination occurs.

## Static Assets

| Path | Contents | Purpose |
|---|---|---|
| `/static/pyodide-extra/index.json` | Normalized name -> filename map for pyodide-extra wheels | Model resolves wheel URLs via pyfetch |
| `/static/pyodide-extra/*.whl` | LLENS additional wheels | pyfetch + micropip.install |
| `/static/fonts/NotoSansJP-Regular.ttf` | Noto Sans JP Regular (OFL, ~2.3MB) | Japanese output for matplotlib / fpdf2 |
| `/pyodide/*.whl` | OWUI bundle wheels | Auto-loaded via import |
| `/pyodide/pyodide-lock.json` | Pyodide official lock (340 entries, **only 46 have actual files**) | See pitfall above |

## Prompt Override

OWUI v0.9.5's `CODE_INTERPRETER_PYODIDE_PROMPT` constant cannot be
overridden via environment variables. At build time,
`docker/open-webui/patch-pyodide-prompt.py` patches `config.py` via sed
to inject the contents of `prompts/code-interpreter.md` (LLENS is
designed to allow micropip.install via `/static/pyodide-extra/`, so the
original "Do not install packages" directive must be disabled).

When upgrading OWUI, the patch script's docstring contains a **snapshot
of the original prompt as of v0.9.5**. Diff it against the upstream new
version to ensure nothing is missed.

## Commands for Adding and Verifying

```sh
# List what is bundled in the OWUI bundle
docker exec llens-open-webui ls /app/build/pyodide/ | grep '\.whl$' \
  | awk -F- '{n=$1; v=$2; gsub(/[.]whl$/,"",v); printf "%-25s %s\n", n, v}' | sort

# LLENS pyodide-extra (index.json)
docker exec llens-open-webui cat /app/build/static/pyodide-extra/index.json | python3 -m json.tool

# Check Pyodide ABI / version
docker exec llens-open-webui python3 -c '
import json; d=json.load(open("/app/build/pyodide/pyodide-lock.json"))["info"]
for k in ("version","python","abi_version","platform"): print(k, d[k])'
```
