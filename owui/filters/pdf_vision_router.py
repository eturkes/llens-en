"""
title: PDF Vision Router
author: Ken Enda
version: 0.7.0
required_open_webui_version: 0.5.0
description: |
  Routes PDF processing according to the following rules:

    No text layer          : Rasterize all pages + VLM (image_only, no page limit)
    Has text + <=30 pages  : Rasterize all pages + VLM + Docling (hybrid)
    Has text + 31+ pages   : Docling only (text_only)

  Docling results are always preserved (_exclude is not called).
  Which route was taken is visible via model-directed notes.

changelog:
  0.7.0: No-text route removes page limit; text-present cap raised from 10p to 30p.
         text_only route also injects a model-directed note for clarity. Notes simplified overall.
  0.6.0: Rule change. No-text rasterizes all pages without limit. Docling always preserved.
  0.5.0: Hybrid mode introduced. Text-present PDFs also use VLM if <=5 pages.
  0.4.0: Unified logging to print, added full messages dump.
  0.3.0: Use body['files'][i]['file']['path'] directly.
  0.2.0: Changed file retrieval to direct DB read.
  0.1.0: Initial version.
"""

import io
import os
import base64
import logging
import traceback
from typing import Optional

import pypdf
from pdf2image import convert_from_bytes
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _p(msg: str, level: str = "info"):
    """Log output. OpenWebUI intercepts standard logging via loguru,
    so calling logger.info/warning/error is sufficient."""
    getattr(logger, level)(f"[PDF-Router] {msg}")


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Priority when multiple Filters apply to the same model (lower = first)",
        )
        text_layer_char_threshold: int = Field(
            default=100,
            description=(
                "If total characters extracted from all PDF pages are below this, "
                "the PDF is considered to have no text layer"
            ),
        )
        hybrid_page_limit: int = Field(
            default=30,
            description=(
                "For text-present PDFs, VLM rasterization is also used (hybrid) if page count "
                "is at or below this limit. Above this, Docling only (text_only). "
                "No limit for text-absent PDFs."
            ),
        )
        rasterize_dpi: int = Field(
            default=200,
            description="Page rasterization DPI. Higher = more accuracy, more token consumption",
        )
        dump_messages: bool = Field(
            default=False,
            description="Dump messages summary at inlet entry/exit (for debugging)",
        )

    def __init__(self):
        self.file_handler = False
        self.valves = self.Valves()

    # ============================================================
    # Messages summary dump (abbreviated)
    # ============================================================
    def _dump_messages(self, body: dict, when: str):
        msgs = body.get("messages", [])
        summary = []
        for i, m in enumerate(msgs):
            role = m.get("role")
            content = m.get("content")
            if isinstance(content, str):
                summary.append(f"[{i}]{role}:str({len(content)})")
            elif isinstance(content, list):
                parts = []
                for c in content:
                    if not isinstance(c, dict):
                        parts.append(type(c).__name__)
                        continue
                    t = c.get("type")
                    if t == "text":
                        parts.append(f"text({len(c.get('text', ''))})")
                    elif t == "image_url":
                        url = c.get("image_url", {}).get("url", "")
                        parts.append(
                            f"img(data,{len(url)})"
                            if url.startswith("data:")
                            else "img(url)"
                        )
                    else:
                        parts.append(str(t))
                summary.append(f"[{i}]{role}:[{','.join(parts)}]")
            else:
                summary.append(f"[{i}]{role}:{type(content).__name__}")
        _p(f"messages ({when}, n={len(msgs)}): {' '.join(summary)}")

    # ============================================================
    # Collect PDFs from body
    # ============================================================
    def _collect_pdf_files(self, body: dict) -> list[dict]:
        seen_ids = set()
        results = []

        for src_key in ("files", "metadata_files"):
            if src_key == "metadata_files":
                src = (body.get("metadata") or {}).get("files") or []
            else:
                src = body.get("files") or []

            for f in src:
                if not isinstance(f, dict):
                    continue
                file_inner = f.get("file") or {}
                file_id = f.get("id") or file_inner.get("id")
                filename = file_inner.get("filename") or f.get("name") or ""
                path = file_inner.get("path")

                if not filename.lower().endswith(".pdf"):
                    continue
                if not file_id or not path or file_id in seen_ids:
                    if file_id and file_id not in seen_ids:
                        _p(
                            f"Skipping {filename!r}: missing id/path "
                            f"(id={file_id}, path={path!r})",
                            level="warning",
                        )
                    continue

                seen_ids.add(file_id)
                results.append({"id": file_id, "name": filename, "path": path})

        return results

    # ============================================================
    # PDF analysis
    # ============================================================
    def _analyze_pdf(self, pdf_bytes: bytes) -> tuple[bool, int, int]:
        """returns (has_text, n_pages, total_chars)"""
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            n_pages = len(reader.pages)
            total_chars = 0
            for page in reader.pages:
                try:
                    txt = page.extract_text() or ""
                    total_chars += len(txt.strip())
                except Exception:
                    pass  # Silently continue on per-page exceptions
            has_text = total_chars >= self.valves.text_layer_char_threshold
            return has_text, n_pages, total_chars
        except Exception as e:
            _p(f"PDF analysis failed, treating as image PDF: {e}", level="warning")
            return False, 0, 0

    # ============================================================
    # Rasterization
    # ============================================================
    def _rasterize(self, pdf_bytes: bytes) -> list[str]:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=self.valves.rasterize_dpi,
            fmt="png",
        )
        urls = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            urls.append(f"data:image/png;base64,{b64}")
        return urls

    # ============================================================
    # Inject images and notes into the last user message
    # ============================================================
    def _inject(
        self,
        body: dict,
        images: list[dict],
        notes: list[str],
    ):
        messages = body.get("messages", [])
        if not messages:
            _p("messages is empty, cannot inject", level="warning")
            return

        last_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_idx = i
                break
        if last_idx is None:
            _p("No user message found, cannot inject", level="warning")
            return

        last_msg = messages[last_idx]
        existing = last_msg.get("content", "")

        if isinstance(existing, str):
            new_content = [{"type": "text", "text": existing}] if existing else []
        elif isinstance(existing, list):
            new_content = list(existing)
        else:
            new_content = []

        if notes:
            new_content.append(
                {
                    "type": "text",
                    "text": (
                        "\n\n[System Note / PDF Vision Router]\n" + "\n".join(notes)
                    ),
                }
            )
        new_content.extend(images)
        messages[last_idx]["content"] = new_content
        body["messages"] = messages

    # ============================================================
    # inlet
    # ============================================================
    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
    ) -> dict:
        try:
            if self.valves.dump_messages:
                self._dump_messages(body, when="inlet entry")

            pdf_files = self._collect_pdf_files(body)
            if not pdf_files:
                return body

            _p(
                f"inlet model={body.get('model')} "
                f"user={(__user__ or {}).get('id')} "
                f"pdfs={len(pdf_files)}"
            )

            injected_images: list[dict] = []
            injected_notes: list[str] = []

            for c in pdf_files:
                fname = c["name"]
                path = c["path"]

                # 1. Read file
                if not os.path.exists(path):
                    _p(f"{fname}: path does not exist -> leaving to Docling", level="error")
                    continue
                try:
                    with open(path, "rb") as f:
                        pdf_bytes = f.read()
                except Exception as e:
                    _p(f"{fname}: read failed -> leaving to Docling: {e}", level="error")
                    continue

                # 2. Analysis
                has_text, n_pages, total_chars = self._analyze_pdf(pdf_bytes)
                if n_pages == 0:
                    _p(f"{fname}: analysis failed -> leaving to Docling", level="warning")
                    continue

                # ============================================
                # Routing
                #   No text          -> Rasterize (image_only, no page limit)
                #   Has text & <= N  -> Rasterize (hybrid)
                #   Has text & > N   -> Docling only (text_only)
                #   Docling is always preserved
                # ============================================
                limit = self.valves.hybrid_page_limit

                if has_text and n_pages > limit:
                    _p(
                        f"{fname}: text_only "
                        f"(pages={n_pages}>{limit}, chars={total_chars})"
                    )
                    injected_notes.append(
                        f"* {fname} ({n_pages}p, {total_chars} chars): Long document, "
                        f"Docling extraction only (rasterization omitted). "
                        f"Text in figures/tables, handwriting, and stamps are not processed."
                    )
                    continue

                mode = "hybrid" if has_text else "image_only"
                _p(
                    f"{fname}: {mode} "
                    f"(pages={n_pages}, chars={total_chars}, has_text={has_text})"
                )

                try:
                    data_urls = self._rasterize(pdf_bytes)
                except Exception as e:
                    _p(
                        f"{fname}: rasterization failed -> leaving to Docling: {e}",
                        level="error",
                    )
                    _p(traceback.format_exc(), level="error")
                    continue

                for url in data_urls:
                    injected_images.append(
                        {"type": "image_url", "image_url": {"url": url}}
                    )

                if has_text:
                    injected_notes.append(
                        f"* {fname} ({n_pages}p, {total_chars} chars): "
                        f"Docling extraction + all pages rasterized. "
                        f"Supplement text in figures/tables, handwriting, and stamps from images. "
                        f"Advise original document verification."
                    )
                else:
                    injected_notes.append(
                        f"* {fname} ({n_pages}p): Scanned PDF, all pages provided as images only. "
                        f"Advise original document verification."
                    )
                # Docling is always preserved -> _exclude is not called

            # Injection
            if injected_images or injected_notes:
                _p(
                    f"Injection: {len(injected_images)} image(s), "
                    f"{len(injected_notes)} note(s)"
                )
                self._inject(body, injected_images, injected_notes)
                if self.valves.dump_messages:
                    self._dump_messages(body, when="inlet exit")

            return body

        except Exception as e:
            _p(f"Exception in entire inlet: {e}", level="error")
            _p(traceback.format_exc(), level="error")
            return body
