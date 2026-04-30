"""Email adapter — ingests .eml email files."""

from __future__ import annotations

import email as email_lib
import email.policy
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ContentItemResult
from app.models.content_item import ContentItem
from app.models.content_segment import ContentSegment
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


def _extract_text_body(msg: email_lib.message.Message) -> list[str]:
    """Return list of text/plain body parts, decoded."""
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="replace"))
    else:
        if msg.get_content_type() == "text/plain":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                parts.append(payload.decode(charset, errors="replace"))
    return parts


class EmailAdapter:
    source_type = "email"
    display_name = "Email (.eml)"
    accepted_mimes = ["message/rfc822", "text/x-eml"]
    accepted_extensions = [".eml"]
    supported_export_formats = ["txt", "md", "json"]

    async def ingest(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        options: dict[str, Any],
        storage: StorageBackend,
    ) -> ContentItemResult:
        upload = options["upload"]
        title_override = options.get("title")

        raw_bytes = await upload.read()
        msg = email_lib.message_from_bytes(raw_bytes, policy=email_lib.policy.default)

        subject = str(msg.get("Subject", "")) or "Untitled Email"
        from_addr = str(msg.get("From", ""))
        date_str = str(msg.get("Date", ""))
        title = title_override or subject

        body_parts = _extract_text_body(msg)
        if not body_parts:
            body_parts = ["[No text content found in this email]"]

        # Split each body part into paragraphs (double newline)
        segments_text: list[str] = []
        for part in body_parts:
            for paragraph in part.split("\n\n"):
                paragraph = paragraph.strip()
                if paragraph:
                    segments_text.append(paragraph)
        if not segments_text:
            segments_text = [body_parts[0]]

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/original", raw_bytes)
        segments_data = [
            {"id": idx, "start": 0.0, "end": 0.0, "text": text, "speaker": None}
            for idx, text in enumerate(segments_text)
        ]
        output_uri = await storage.store(
            user_id,
            item_id,
            "output/segments.json",
            json.dumps({"segments": segments_data, "created_at": now.isoformat()}, indent=2),
        )
        body_text = "\n\n".join(segments_text)
        await storage.store(user_id, item_id, "output/content.txt", body_text)

        item = ContentItem(
            id=item_id,
            user_id=user_id,
            adapter_type=self.source_type,
            title=title,
            source_material_path=source_uri,
            source_material_mime="message/rfc822",
            source_material_size=len(raw_bytes),
            output_content_path=output_uri,
            status="ready",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        await db.flush()

        for segment in segments_data:
            db.add(
                ContentSegment(
                    content_item_id=item_id,
                    segment_index=segment["id"],
                    start_time=0.0,
                    end_time=0.0,
                    speaker=None,
                    text=segment["text"],
                )
            )
        await db.flush()

        from app.services.content_service import index_content_segments

        try:
            await index_content_segments(item_id, self.source_type, db, segments=segments_data)
        except Exception:
            logger.exception("FTS indexing failed for %s", item_id)

        logger.info(
            "EmailAdapter: %d segments, item_id=%s (from=%s, date=%s)",
            len(segments_text),
            item_id,
            from_addr,
            date_str,
        )
        return ContentItemResult(
            content_item_id=item_id, title=title, segment_count=len(segments_text)
        )
