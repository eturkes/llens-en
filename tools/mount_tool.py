"""
title: Mount Tools
description: 添付ファイルの docling 抽出テキストを .md として登録し、Pyodide の /mnt/uploads/ に出現させる。既存ファイルの /mnt 再マウントも行う。
author: Ken Enda
version: 0.2.0
required_open_webui_version: 0.5.0

changelog:
  0.2.0: 1) chat:message:files を emit するだけだったのを、OWUI 公式パターン
            (tools/builtin.py の画像生成 tool) に合わせて
            Chats.add_message_files_by_id_and_message_id() で chat 履歴 DB に
            persist してから emit するよう修正。これまで添付がメッセージに永続化されず、
            ターン跨ぎ・reload・Pyodide の /mnt/uploads 取り込みに不安定だった。
         2) mount_markdown / mount_file に __chat_id__ / __message_id__ 引数を追加
            (OWUI が tool 呼び出し時に自動 inject する context)。
         3) Storage.upload_file の旧 2-arg signature 試行を撤去し、新シグネチャ
            (file, filename, tags) 一本化。古い OWUI との互換は捨てる。
         4) replace_message_files valve を削除。OWUI 公開 API は append 系のみで、
            既存添付を消す経路が無いため (DB を直接書き換えるしかなくなる)
            valve を残しても無意味と判断。
  0.1.0: 初版。
"""

# =============================================================================
# 仕組み（なぜこれで /mnt に出るのか）
# -----------------------------------------------------------------------------
# Pyodide の /mnt/uploads/ はブラウザ側（IDBFS）にある。バックエンドの Tool は
# そこへ直接書けない。ファイルが /mnt に出る唯一の経路は:
#   1. Open WebUI に「実ファイル（file_id 付き・/content で取得可能）」として登録
#   2. そのファイルを assistant message の files に persist + UI 通知
#   3. コード実行前にフロントが getFileContentById() で取得し Pyodide FS へ展開
# 本ツールは 1 を Files API、2 を Chats.add_message_files_by_id_and_message_id +
# chat:message:files event で行う (= OWUI 同梱の画像生成 tool と同じパターン)。
# persist と event の両方を出すことで、同一ターンの即時表示と、ターン跨ぎ /
# reload 後の永続表示の両方を担保する。
# =============================================================================

import io
import logging
import os
import uuid
from typing import Optional, Callable, Any, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Open WebUI 内部 API（ランタイムで解決される） ---------------------------
try:
    from open_webui.models.chats import Chats
    from open_webui.models.files import Files, FileForm
    from open_webui.storage.provider import Storage
except Exception:  # ローカルでの静的解析用フォールバック
    Chats = None
    Files = None
    FileForm = None
    Storage = None


# -----------------------------------------------------------------------------
# 低レベルヘルパ
# -----------------------------------------------------------------------------
def _storage_upload(data: bytes, filename: str):
    """Storage.upload_file (file, filename, tags) を呼び (contents, path) を返す。
    OWUI 0.5+ は tags 引数必須 (provider.py の abstractmethod 定義通り)。"""
    return Storage.upload_file(io.BytesIO(data), filename, {})


def _register_text_file(user_id: str, display_name: str, text: str,
                        content_type: str = "text/markdown") -> dict:
    """テキストを実ファイルとして Storage + Files に登録し、
    フロントの files ストアに渡せる添付 dict を返す。
    .md の中身は data.content と Storage 実体の両方に入れる
    （/content は Storage 実体を返すため、これがないと取得できない）。"""
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
    """メッセージ files ストアに入れる添付オブジェクト。
    （※ 形は version 依存。UI に出ない場合はここを調整）"""
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
    """ツールに渡るチャットコンテキストのファイル参照を正規化して列挙。
    __files__ と metadata.files の両方をフォールバックで見る。"""
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
    """filename 指定が無ければ全件、あれば部分一致（大小無視）。"""
    if not target:
        return True
    if not name:
        return False
    return target.lower() in name.lower()


# -----------------------------------------------------------------------------
# Tool 本体
# -----------------------------------------------------------------------------
class Tools:
    class Valves(BaseModel):
        markdown_suffix: str = Field(
            default=".md", description="派生テキストファイルの拡張子")
        debug: bool = Field(default=False, description="詳細ログを status で流す")

    class UserValves(BaseModel):
        enabled: bool = Field(default=True, description="ユーザー側の有効/無効")

    def __init__(self):
        self.valves = self.Valves()

    # ---- 共通: persist + chat:message:files の発火 -------------------------
    async def _persist_and_emit_files(
        self, attachments, chat_id, message_id, __event_emitter__,
    ):
        """新規添付をメッセージに反映。OWUI 標準パターン:
        1) Chats.add_message_files_by_id_and_message_id() で chat 履歴 DB に append
           (既存 message.files に新規ぶんだけ追加。返り値は merged list)
        2) chat:message:files event で UI に即時反映 (merged list を流す)
        chat_id / message_id が無ければ persist をスキップして emit だけ行う
        (tool テスト用フォールバック)。"""
        # OWUI root logger は WARNING のため、診断は error レベルで出す (token_meter と同パターン)
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
                logger.error(f"[mount_tool] persist failed: {e!r} (emit のみで継続)")
        else:
            logger.error(
                f"[mount_tool] persist SKIP "
                f"(Chats={Chats is not None}, chat_id={bool(chat_id)}, "
                f"message_id={bool(message_id)}) — emit のみ"
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
        添付ドキュメントの docling 抽出済みテキストを Markdown ファイル(.md)として
        登録し、コードインタプリタの /mnt/uploads/ に出現させる。
        モデルに大量本文を逐語転記させず、コードからファイルとして読ませたい時に使う。
        **コードを書く前に必ず呼ぶこと。** 戻り値に /mnt 上のパスを返す。

        :param filename: 対象ファイル名（部分一致）。省略時は添付全件を対象。
        """
        if Files is None:
            return "ERROR: open_webui の内部 API を解決できません（実行環境を確認）。"
        if not __user__ or not __user__.get("id"):
            return "ERROR: ユーザー情報が取得できませんでした。"

        ctx_count = sum(1 for _ in _iter_context_files(__files__, __metadata__))
        logger.error(
            f"[mount_tool] mount_markdown entry filter={filename!r} "
            f"chat_id={__chat_id__!r} message_id={__message_id__!r} "
            f"ctx_files={ctx_count}"
        )

        await self._status("Resolving attached files...", False, __event_emitter__)

        made = []
        report = []

        for fid, fname, _ref in _iter_context_files(__files__, __metadata__):
            if not _match(fname, filename):
                continue
            rec = Files.get_file_by_id(fid)
            if not rec:
                report.append(f"- {fname or fid}: レコード無し（skip）")
                continue
            content = (getattr(rec, "data", None) or {}).get("content")
            if not content:
                report.append(
                    f"- {fname or fid}: 抽出テキストが空（docling 未完了 or 失敗）")
                continue
            stem = os.path.splitext(fname or f"file_{fid[:8]}")[0]
            md_name = f"{stem}{self.valves.markdown_suffix}"
            try:
                att = _register_text_file(__user__["id"], md_name, content)
                made.append(att)
                report.append(f"- {md_name}: /mnt/uploads/{md_name}")
            except Exception as e:
                report.append(f"- {md_name}: 登録失敗 {e!r}")

        if not made:
            await self._status("No markdown mounted.", True, __event_emitter__)
            return "マウント対象がありませんでした。\n" + "\n".join(report)

        await self._persist_and_emit_files(
            made, __chat_id__, __message_id__, __event_emitter__,
        )
        await self._status(f"Mounted {len(made)} markdown file(s).", True,
                           __event_emitter__)
        return (
            f"{len(made)} 件の Markdown を /mnt/uploads/ にマウントしました。\n"
            + "\n".join(report)
            + "\n\nコード側で次のように読めます:\n"
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
        チャットコンテキストの既存ファイル（アップロード済み or ナレッジ）を
        /mnt/uploads/ にマウントする。file_context を切っていて自動マウントされない、
        あるいは過去ターンのファイルを再度 /mnt に出したい場合に使う。
        **コードを書く前に呼ぶこと。**

        :param filename: マウントしたいファイル名（部分一致）。
        """
        if Files is None:
            return "ERROR: open_webui の内部 API を解決できません。"
        if not __user__ or not __user__.get("id"):
            return "ERROR: ユーザー情報が取得できませんでした。"

        ctx_count = sum(1 for _ in _iter_context_files(__files__, __metadata__))
        logger.error(
            f"[mount_tool] mount_file entry filter={filename!r} "
            f"chat_id={__chat_id__!r} message_id={__message_id__!r} "
            f"ctx_files={ctx_count}"
        )

        targets = []
        report = []

        for fid, fname, ref in _iter_context_files(__files__, __metadata__):
            if not _match(fname, filename):
                continue
            rec = Files.get_file_by_id(fid)
            if not rec:
                report.append(f"- {fname or fid}: レコード無し（skip）")
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
            return (f"'{filename}' に一致する既存ファイルが見つかりませんでした。\n"
                    + "\n".join(report))

        await self._persist_and_emit_files(
            targets, __chat_id__, __message_id__, __event_emitter__,
        )
        await self._status(f"Mounted {len(targets)} file(s).", True,
                           __event_emitter__)
        return (f"{len(targets)} 件を /mnt/uploads/ にマウントしました。\n"
                + "\n".join(report))
