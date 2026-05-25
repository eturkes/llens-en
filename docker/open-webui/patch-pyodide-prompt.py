#!/usr/bin/env python3
"""
Replaces the hardcoded CODE_INTERPRETER_PYODIDE_PROMPT in OWUI with the
LLENS specification (contents of prompts/code-interpreter.md). Run at build time.

The original prompt blanket-bans package installation ("Do not install packages
-- pip install, subprocess, and micropip.install() are not available"), which
conflicts with LLENS's design of installing wheels via micropip.install from
/static/pyodide-extra/.

Uses prompts/code-interpreter.md as the single source of truth and injects its
contents directly.

- If already patched to LLENS version, this is a no-op (idempotent)
- If the target pattern is not found or the source md is missing, the build fails

------------------------------------------------------------------------
Reference: original OWUI prompt being overwritten (as of v0.9.5)
------------------------------------------------------------------------
When upgrading OWUI, diff the below against the current upstream version and
check whether any changes should be incorporated into our LLENS prompt
(prompts/code-interpreter.md). If the structure changes in a new version,
the regex at the end of this file also needs updating.

Extraction command:
  docker run --rm --entrypoint sh ghcr.io/open-webui/open-webui:<TAG> -c \\
    'python3 -c "import re; print(re.search(r\\"CODE_INTERPRETER_PYODIDE_PROMPT\\\\s*=\\\\s*(\\\\\\"\\\\\\"\\\\\\"[\\\\s\\\\S]*?\\\\\\"\\\\\\"\\\\\\")\\", open(\\"/app/backend/open_webui/config.py\\").read()).group(0))"'

---- ghcr.io/open-webui/open-webui:v0.9.5 ----
CODE_INTERPRETER_PYODIDE_PROMPT = '''

##### Pyodide Environment

- This Python environment runs via Pyodide in the browser. **Do not install packages** --- `pip install`, `subprocess`, and `micropip.install()` are not available.
- If a required library is unavailable, use an alternative approach with available modules. Do not attempt to install anything.

##### Persistent File System

- User-uploaded files are available at `/mnt/uploads/`. When the user asks you to work with their files, read from this directory.
- You can also write output files to `/mnt/uploads/` so the user can access and download them from the file browser.
- The file system persists across code executions within the same session.
- Use `import os; os.listdir('/mnt/uploads')` to discover available files.
'''
------------------------------------------------------------------------
"""
import pathlib
import re
import sys

TARGET = pathlib.Path("/app/backend/open_webui/config.py")
SOURCE = pathlib.Path("/tmp/code-interpreter.md")  # Copied by Dockerfile
# Phrase that only appears after patching, used for idempotent detection
MARKER = "## Code Execution Environment"


def main() -> int:
    if not SOURCE.exists():
        print(f"[patch-pyodide-prompt] ERROR: {SOURCE} not found", file=sys.stderr)
        return 1
    body = SOURCE.read_text().rstrip("\n")

    text = TARGET.read_text()

    if MARKER in text:
        print(f"[patch-pyodide-prompt] already patched, skipping")
        return 0

    pattern = re.compile(
        r'CODE_INTERPRETER_PYODIDE_PROMPT\s*=\s*"""[\s\S]*?"""',
    )
    if not pattern.search(text):
        print(
            f"[patch-pyodide-prompt] ERROR: pattern not found in {TARGET}.\n"
            "  The constant structure may have changed in a newer OWUI version.\n"
            "  Review the regex in docker/open-webui/patch-pyodide-prompt.py.",
            file=sys.stderr,
        )
        return 1

    # Escape if the md body contains triple-quotes (not currently the case, but just in case)
    if '"""' in body:
        print(
            "[patch-pyodide-prompt] ERROR: source md contains triple-quote, "
            "would break Python string literal",
            file=sys.stderr,
        )
        return 1

    new_block = f'CODE_INTERPRETER_PYODIDE_PROMPT = """\n{body}\n"""'
    new_text = pattern.sub(lambda _: new_block, text, count=1)
    TARGET.write_text(new_text)
    print(f"[patch-pyodide-prompt] OK — injected {SOURCE} into {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
