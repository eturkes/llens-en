# LLENS custom Open WebUI image
#
# - Backend (Python 3.11): pdf2image / pypdf added via pip (pinned)
#   Purpose: PDF → image → VLM (Kimi K2.6, etc.) pipeline for Functions/Tools
# - Client Pyodide (Python 3.12 WASM): Office-related wheels served statically
#   /app/build/static/pyodide-extra/*.whl served over same-origin HTTP
#   → micropip can load them in the browser even in an air-gapped environment
#
# When updating versions, sync the FROM tag with the image tag in docker-compose.yml:
#   docker compose build --pull open-webui

FROM ghcr.io/open-webui/open-webui:v0.9.5

# ─────────────────────────────────────────────
# System packages (PDF to image conversion)
# ─────────────────────────────────────────────
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────
# Backend (Python 3.11)
# ─────────────────────────────────────────────
RUN pip install --no-cache-dir \
        pdf2image==1.17.0 \
        pypdf==6.7.5 \
        tiktoken

# ─────────────────────────────────────────────
# Pyodide (browser WASM) wheels for static serving
# ─────────────────────────────────────────────
# Wheels placed in /app/build/static/pyodide-extra/ are served over same-origin HTTP
# and loaded into browser Pyodide via pyfetch + micropip.install(deps=False).
#
# OWUI 0.9.5 bundled Pyodide = 0.28.0.dev0 / ABI cp313-pyodide_2025_0_wasm32.
# `/app/build/pyodide/` already bundles the following wheels, which are
# auto-loaded from imports via `loadPackagesFromImports` (no redistribution needed):
#   beautifulsoup4 / matplotlib / numpy / pandas / pillow / pytz / regex /
#   scikit-learn / scipy / sympy / tiktoken / typing_extensions
#   (openai / requests / pydantic / httpx etc. for OWUI internal use also included)
#
# Note: pyodide-lock.json lists entries for lxml / jinja2 / markupsafe / pycryptodome
# etc., but OWUI has dropped the wheel files from the bundle, so
# `await micropip.install("lxml")` etc. will fail with 404. Serve them separately below.
#
# Route A: pure-Python wheels (py3-none-any) fetched from PyPI.
RUN mkdir -p /app/build/static/pyodide-extra \
 && pip download \
        --dest /app/build/static/pyodide-extra \
        --no-deps \
        --only-binary=:all: \
        --platform=any \
        --python-version=3.12 \
        openpyxl==3.1.5 \
        et_xmlfile==2.0.0 \
        python-docx==1.2.0 \
        python-pptx==1.0.2 \
        XlsxWriter==3.2.9 \
        fpdf2==2.8.7 \
        defusedxml==0.7.1 \
        pydicom==3.0.2 \
        chardet==7.4.3 \
        Jinja2==3.1.6 \
        segno==1.6.6 \
        sqlglot==30.8.0

# Route B: C-extension packages requiring Pyodide-specific emscripten builds (not on PyPI).
# Fetched directly from Pyodide upstream (jsdelivr v0.28.0/full) with ABI 2025_0 wheels.
# OWUI bundled Pyodide (0.28.0.dev0) and v0.28.0 differ in revision but share the same ABI
# (cp313-pyodide_2025_0_wasm32), so imports are compatible.
# Loaded via pyfetch, so pyodide-lock.json sha256 verification does not apply (irrelevant).
ARG PYODIDE_CDN=https://cdn.jsdelivr.net/pyodide/v0.28.0/full
RUN for whl in \
        lxml-5.4.0-cp313-cp313-pyodide_2025_0_wasm32.whl \
        markupsafe-3.0.2-cp313-cp313-pyodide_2025_0_wasm32.whl \
        pycryptodome-3.21.0-cp36-abi3-pyodide_2025_0_wasm32.whl ; do \
        curl -fSL -o "/app/build/static/pyodide-extra/$whl" "$PYODIDE_CDN/$whl" ; \
    done

# Auto-generate index.json: {PEP 503 normalized name: wheel filename}.
# The model only needs to list package names; the browser resolves them
# to exact wheel filenames via this index (prevents filename hallucination).
RUN python -c "import json, pathlib, re; \
d = pathlib.Path('/app/build/static/pyodide-extra'); \
idx = {re.sub(r'[-_.]+', '-', w.name.split('-')[0]).lower(): w.name \
       for w in sorted(d.glob('*.whl'))}; \
(d / 'index.json').write_text(json.dumps(idx, indent=2, sort_keys=True) + '\n'); \
print('index.json:', json.dumps(idx, indent=2, sort_keys=True))"

# ─────────────────────────────────────────────
# Japanese font (for matplotlib / fpdf2)
# ─────────────────────────────────────────────
# Pyodide has no fonts with Japanese glyphs, so matplotlib plots and fpdf2
# PDF output render Japanese as tofu (□). Serve an OFL-licensed Noto Sans JP
# Regular OTF from same-origin /static/fonts/ and load it via pyfetch in the prompt.
# Official notofonts/noto-cjk Japanese subset OTF, ~4.5MB (the version where
# the family name is correctly set to "Noto Sans JP". The fontsource TTF of the
# same name has the family name "Noto Sans JP Thin", which breaks matplotlib lookup).
RUN mkdir -p /app/build/static/fonts \
 && curl -fSL \
        -o /app/build/static/fonts/NotoSansJP-Regular.otf \
        https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf

# ─────────────────────────────────────────────
# Replace OWUI hardcoded prompt
# ─────────────────────────────────────────────
# CODE_INTERPRETER_PYODIDE_PROMPT is a string constant that cannot be overridden via env,
# containing "Do not install packages ... micropip.install() are not available".
# LLENS allows micropip via /static/pyodide-extra/, so we replace the constant block
# with the content of prompts/code-interpreter.md (= single source of truth).
# Build context is repo root, so COPY paths are relative to the repo.
COPY docker/open-webui/patch-pyodide-prompt.py /tmp/patch-pyodide-prompt.py
COPY prompts/code-interpreter.md /tmp/code-interpreter.md
RUN python /tmp/patch-pyodide-prompt.py \
 && rm /tmp/patch-pyodide-prompt.py /tmp/code-interpreter.md
