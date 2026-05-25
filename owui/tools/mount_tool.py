"""
title: Mount Tools
description: Registers docling-extracted text from attached files as .md and makes them appear in Pyodide's /mnt/uploads/. Also re-mounts existing files to /mnt.
author: Ken Enda
version: 0.2.0
required_open_webui_version: 0.5.0

changelog:
  0.2.0: 1) Changed from merely emitting chat:message:files to the official OWUI pattern
            (tools/builtin.py image generation tool) using
            Chats.add_message_files_by_id_and_message_id() to persist to the chat
            history DB before emitting. Previously attachments were not persisted to
            messages, causing instability across turns, on reload, and in Pyodide's
            /mnt/uploads incorporation.
         2) Added __chat_id__ / __message_id__ arguments to mount_markdown / mount_file
            (context auto-injected by OWUI at tool invocation).
         3) Removed the old 2-arg signature attempt for Storage.upload_file; unified to
            new signature (file, filename, tags). Backward compatibility with older
            OWUI is dropped.
         4) Removed replace_message_files valve. The OWUI public API only has append
            operations and there is no path to delete existing attachments (would require
            direct DB modification), so keeping the valve was pointless.
         5) When __files__ / __metadata__.files are empty, the tool now walks the chat
            history using __chat_id__ to use files attached in previous turns as a
            fallback. OWUI middleware only puts "files submitted this turn" into
            __files__, so when the tool is called in turns after the user's attachment,
            ctx_files=0 and nothing could be processed.
  0.1.0: Initial version.
"""

# =============================================================================
# How it works (why files appear in /mnt)
# -----------------------------------------------------------------------------
# Pyodide's /mnt/uploads/ exists in the browser (IDBFS). The backend Tool cannot
# write there directly. The only path for files to appear in /mnt is:
#   1. Register as a "real file (with file_id, retrievable via /content)" in Open WebUI
#   2. Persist that file to the assistant message's files + UI notification
#   3. Before code execution, the frontend fetches via getFileContentById() and
#      deploys to the Pyodide FS
# This tool does step 1 via the Files API, and step 2 via
# Chats.add_message_files_by_id_and_message_id + chat:message:files event
# (= same pattern as OWUI's built-in image generation tool).
# Both persist and event are emitted to ensure both immediate display in the same
# turn and persistent display across turns / after reload.
# =============================================================================

import io
import logging
import os
import uuid
from typing import Optional, Callable, Any, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Open WebUI internal API (resolved at runtime) ---------------------------
try:
    from open_webui.models.chats import Chats
    from open_webui.models.files import Files, FileForm
    from open_webui.storage.provider import Storage
except Exception:  # Fallback for local static analysis
    Chats = None
    Files = None
    FileForm = None
    Storage = None


# -----------------------------------------------------------------------------
# Low-level helpers
# -----------------------------------------------------------------------------
def _storage_upload(data: bytes, filename: str):
    """Call Storage.upload_file (file, filename, tags) and return (contents, path).
    OWUI 0.5+ requires the tags argument (per provider.py abstractmethod definition)."""
    return Storage.upload_file(io.BytesIO(data), filename, {})


def _register_text_file(user_id: str, display_name: str, text: str,
                        content_type: str = "text/markdown") -> dict:
    """Register text as a real file in Storage + Files and return an attachment
    dict suitable for the frontend files store.
    The .md content is stored in both data.content and the Storage entity
    (since /content returns the Storage entity, without this retrieval fails)."""
    file_id = str(uuid.uuid4())
    raw = text.encode("utf-8")
    stored_name = f"{file_id}_{display_name}"
    contents, path = _storage_upload(raw, stored_name)

    Files.insert_new_file(
        user_id,
        FileForm(
            **{
                "id": file_id,
                "filename": display_name,
                "path": path,
                "data": {"content": text},
                "meta": {
                    "name": display_name,
                    "content_type": content_type,
                    "size": len(raw),
                },
            }
        ),
    )
    return _attachment_dict(file_id, display_name, content_type, len(raw))


def _attachment_dict(file_id: str, name: str, content_type: str, size: int) -> dict:
    """Attachment object for the message files store.
    (Note: format is version-dependent. Adjust here if not appearing in the UI)"""
    return {
        "type": "file",
        "id": file_id,
        "name": name,
        "status": "uploaded",
        "url": f"/api/v1/files/{file_id}",
        "error": "",
        "itemId": str(uuid.uuid4()),
        "file": {
            "id": file_id,
            "filename": name,
            "meta": {"name": name, "content_type": content_type, "size": size},
        },
    }


def _iter_context_files(__files__, __metadata__):
    """Normalize and iterate file references from the chat context passed to the tool.
    Falls back to both __files__ and metadata.files."""
    raw = []
    if __files__:
        raw = __files__
    elif __metadata__ and __metadata__.get("files"):
        raw = __metadata__["files"]
    for f in raw or []:
        inner = f.get("file", {}) if isinstance(f, dict) else {}
        fid = (f.get("id") if isinstance(f, dict) else None) or inner.get("id")
        fname = (f.get("name") if isinstance(f, dict) else None) \
            or inner.get("filename") or (inner.get("meta") or {}).get("name")
        if fid:
            yield fid, fname, f


def _match(name: Optional[str], target: Optional[str]) -> bool:
    """If no filename specified, match all; otherwise case-insensitive substring match."""
    if not target:
        return True
    if not name:
        return False
    return target.lower() in name.lower()


# -----------------------------------------------------------------------------
# Tool body
# -----------------------------------------------------------------------------
class Tools:
    class Valves(BaseModel):
        markdown_suffix: str = Field(
            default=".md", description="File extension for derived text files")
        debug: bool = Field(default=False, description="Stream detailed logs via status")

    class UserValves(BaseModel):
        enabled: bool = Field(default=True, description="User-side enable/disable")

    def __init__(self):
        self.valves = self.Valves()

    # ---- Common: persist + chat:message:files emission -------------------------
    async def _persist_and_emit_files(
        self, attachments, chat_id, message_id, __event_emitter__,
    ):
        """Reflect new attachments on the message. OWUI standard pattern:
        1) Chats.add_message_files_by_id_and_message_id() appends to chat history DB
           (adds only new items to existing message.files; returns merged list)
        2) chat:message:files event for immediate UI reflection (sends merged list)
        If chat_id / message_id are missing, skip persist and emit only
        (fallback for tool testing)."""
        # OWUI root logger is WARNING, so diagnostics use error level (same pattern as token_meter)
        merged = list(attachments)
        persisted = False
        if Chats is not None and chat_id and message_id:
            try:
                result = await Chats.add_message_files_by_id_and_message_id(
                    chat_id, message_id, list(attachments),
                )
                if result is not None:
                    merged = result
                persisted = True
            except Exception as e:
                logger.error(f"[mount_tool] persist failed: {e!r} (continuing with emit only)")
        else:
            logger.error(
                f"[mount_tool] persist SKIP "
                f"(Chats={Chats is not None}, chat_id={bool(chat_id)}, "
                f"message_id={bool(message_id)}) — emit only"
            )

        emitted = False
        if __event_emitter__:
            await __event_emitter__({
                "type": "chat:message:files",
                "data": {"files": merged},
            })
            emitted = True

        logger.error(
            f"[mount_tool] _persist_and_emit_files done "
            f"(new={len(attachments)}, merged={len(merged)}, "
            f"persisted={persisted}, emitted={emitted})"
        )

    async def _status(self, msg, done, __event_emitter__):
        if self.valves.debug and __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": msg, "done": done},
            })

    # ---- Context files resolution -----------------------------------------------
    async def _resolve_context_files(
        self,
        __files__: Optional[list],
        __metadata__: Optional[dict],
        __chat_id__: Optional[str],
        __user__: Optional[dict],
    ) -> list:
        """Resolve the file list from the tool's context.
        1) Prefer __files__ / __metadata__.files (files submitted this turn)
        2) When empty, fetch chat history via __chat_id__ and walk each message's
           files to collect attachments from previous turns (deduplicated by id)
        Returns a list of (file_id, filename, raw_dict) same as _iter_context_files."""
        direct = list(_iter_context_files(__files__, __metadata__))
        if direct:
            return direct
        if Chats is None or not __chat_id__:
            return []
        try:
            uid = (__user__ or {}).get("id")
            if uid:
                chat = await Chats.get_chat_by_id_and_user_id(__chat_id__, uid)
            else:
                chat = await Chats.get_chat_by_id(__chat_id__)
        except Exception as e:
            logger.error(f"[mount_tool] chat history lookup failed: {e!r}")
            return []
        if chat is None:
            return []

        messages = (getattr(chat, "chat", None) or {}).get("history", {}).get("messages", {})
        history_files: list = []
        seen: set = set()
        for m in messages.values():
            for f in m.get("files") or []:
                if not isinstance(f, dict):
                    continue
                fid = f.get("id") or (f.get("file") or {}).get("id")
                if fid and fid not in seen:
                    seen.add(fid)
                    history_files.append(f)

        resolved = list(_iter_context_files(history_files, None))
        if resolved:
            logger.error(
                f"[mount_tool] history fallback hit "
                f"chat_id={__chat_id__} files={len(resolved)}"
            )
        return resolved

    # =========================================================================
    # mount_markdown
    # =========================================================================
    async def mount_markdown(
        self,
        filename: Optional[str] = None,
        __user__: Optional[dict] = None,
        __files__: Optional[list] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ) -> str:
        """
        Registers docling-extracted text from attached documents as Markdown files (.md)
        and makes them appear in the code interpreter's /mnt/uploads/.
        Use when you want to let code read files instead of having the model
        transcribe large amounts of text verbatim.
        **Always call before writing code.** Returns the /mnt path in the result.

        :param filename: Target filename (substring match). Omit to process all attachments.
        """
        if Files is None:
            return "ERROR: Cannot resolve open_webui internal API (check execution environment)."
        if not __user__ or not __user__.get("id"):
            return "ERROR: Could not retrieve user information."

        ctx = await self._resolve_context_files(
            __files__, __metadata__, __chat_id__, __user__,
        )
        logger.error(
            f"[mount_tool] mount_markdown entry filter={filename!r} "
            f"chat_id={__chat_id__!r} message_id={__message_id__!r} "
            f"ctx_files={len(ctx)}"
        )

        await self._status("Resolving attached files...", False, __event_emitter__)

        made = []
        report = []

        for fid, fname, _ref in ctx:
            if not _match(fname, filename):
                continue
            rec = Files.get_file_by_id(fid)
            if not rec:
                report.append(f"- {fname or fid}: No record found (skip)")
                continue
            content = (getattr(rec, "data", None) or {}).get("content")
            if not content:
                report.append(
                    f"- {fname or fid}: Extracted text is empty (docling incomplete or failed)")
                continue
            stem = os.path.splitext(fname or f"file_{fid[:8]}")[0]
            md_name = f"{stem}{self.valves.markdown_suffix}"
            try:
                att = _register_text_file(__user__["id"], md_name, content)
                made.append(att)
                report.append(f"- {md_name}: /mnt/uploads/{md_name}")
            except Exception as e:
                report.append(f"- {md_name}: Registration failed {e!r}")

        if not made:
            await self._status("No markdown mounted.", True, __event_emitter__)
            return "No files to mount.\n" + "\n".join(report)

        await self._persist_and_emit_files(
            made, __chat_id__, __message_id__, __event_emitter__,
        )
        await self._status(f"Mounted {len(made)} markdown file(s).", True,
                           __event_emitter__)
        return (
            f"Mounted {len(made)} Markdown file(s) to /mnt/uploads/.\n"
            + "\n".join(report)
            + "\n\nYou can read them from code like this:\n"
            "```python\n"
            "import os\n"
            "print(os.listdir('/mnt/uploads'))\n"
            "md = open('/mnt/uploads/" + made[0]['name'] + "', encoding='utf-8').read()\n"
            "```"
        )

    # =========================================================================
    # mount_file
    # =========================================================================
    async def mount_file(
        self,
        filename: str,
        __user__: Optional[dict] = None,
        __files__: Optional[list] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __chat_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
    ) -> str:
        """
        Mounts an existing file from the chat context (already uploaded or from knowledge)
        to /mnt/uploads/. Use when file_context is disabled and auto-mount does not work,
        or when you want to re-expose a file from a previous turn to /mnt.
        **Call before writing code.**

        :param filename: Filename to mount (substring match).
        """
        if Files is None:
            return "ERROR: Cannot resolve open_webui internal API."
        if not __user__ or not __user__.get("id"):
            return "ERROR: Could not retrieve user information."

        ctx = await self._resolve_context_files(
            __files__, __metadata__, __chat_id__, __user__,
        )
        logger.error(
            f"[mount_tool] mount_file entry filter={filename!r} "
            f"chat_id={__chat_id__!r} message_id={__message_id__!r} "
            f"ctx_files={len(ctx)}"
        )

        targets = []
        report = []

        for fid, fname, ref in ctx:
            if not _match(fname, filename):
                continue
            rec = Files.get_file_by_id(fid)
            if not rec:
                report.append(f"- {fname or fid}: No record found (skip)")
                continue
            meta = (getattr(rec, "meta", None) or {})
            att = _attachment_dict(
                fid,
                fname or rec.filename,
                meta.get("content_type", "application/octet-stream"),
                meta.get("size", 0),
            )
            targets.append(att)
            report.append(f"- {fname or fid}: /mnt/uploads/{fname or rec.filename}")

        if not targets:
            return (f"No existing file matching '{filename}' was found.\n"
                    + "\n".join(report))

        await self._persist_and_emit_files(
            targets, __chat_id__, __message_id__, __event_emitter__,
        )
        await self._status(f"Mounted {len(targets)} file(s).", True,
                           __event_emitter__)
        return (f"Mounted {len(targets)} file(s) to /mnt/uploads/.\n"
                + "\n".join(report))
