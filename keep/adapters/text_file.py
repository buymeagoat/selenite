"""Text File adapter - ingests plain text files without processing."""

from __future__ import annotations

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

_DECODINGS = ["utf-8", "utf-8-sig", "latin-1"]


def _decode(data: bytes) -> str:
    for enc in _DECODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()] or [
        text.strip()
    ]


class TextFileAdapter:
    source_type = "text_file"
    display_name = "Text File"
    accepted_mimes = ["text/plain", "text/markdown", "text/x-rst", "text/x-log"]
    accepted_extensions = [".txt", ".md", ".markdown", ".rst", ".log"]
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

        data = await upload.read()
        text = _decode(data)
        filename = upload.filename or "upload.txt"
        title = (
            title_override
            or filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
            or filename
        )

        paragraphs = _split_paragraphs(text)
        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/original", data)
        segments_data = [
            {"id": index, "start": 0.0, "end": 0.0, "text": paragraph, "speaker": None}
            for index, paragraph in enumerate(paragraphs)
        ]
        output_uri = await storage.store(
            user_id,
            item_id,
            "output/segments.json",
            json.dumps({"segments": segments_data, "created_at": now.isoformat()}, indent=2),
        )
        await storage.store(user_id, item_id, "output/content.txt", text)

        item = ContentItem(
            id=item_id,
            user_id=user_id,
            adapter_type=self.source_type,
            title=title,
            source_material_path=source_uri,
            source_material_mime=upload.content_type or "text/plain",
            source_material_size=len(data),
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

        logger.info("TextFileAdapter: %d paragraphs, item_id=%s", len(paragraphs), item_id)
        return ContentItemResult(
            content_item_id=item_id, title=title, segment_count=len(paragraphs)
        )
