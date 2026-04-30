"""Subtitle File adapter - ingests SRT and VTT files as transcript items."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ContentItemResult
from app.models.content_item import ContentItem
from app.models.content_segment import ContentSegment
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
    r"([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def _ts_to_seconds(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    hours, minutes, seconds = float(parts[0]), float(parts[1]), float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _parse_srt(text: str) -> list[dict[str, Any]]:
    segments = []
    for index, match in enumerate(_SRT_BLOCK_RE.finditer(text)):
        start = _ts_to_seconds(match.group(2))
        end = _ts_to_seconds(match.group(3))
        caption_text = match.group(4).strip()
        if caption_text:
            segments.append(
                {
                    "id": index,
                    "start": start,
                    "end": end,
                    "text": caption_text,
                    "speaker": None,
                }
            )
    return segments


def _parse_vtt(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"WEBVTT.*?\n\n", "", text, count=1, flags=re.DOTALL)
    return _parse_srt(cleaned)


class SubtitleFileAdapter:
    source_type = "subtitle_file"
    display_name = "Subtitle / Transcript File"
    accepted_mimes = ["application/x-subrip", "text/vtt", "text/plain"]
    accepted_extensions = [".srt", ".vtt"]
    supported_export_formats = ["srt", "vtt", "txt", "json"]

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
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")

        filename = upload.filename or "subtitles.srt"
        ext = Path(filename).suffix.lower()
        title = (
            title_override
            or Path(filename).stem.replace("_", " ").replace("-", " ").strip()
            or filename
        )

        if ext == ".vtt":
            segments_data = _parse_vtt(text)
        else:
            segments_data = _parse_srt(text)

        if not segments_data:
            segments_data = [
                {"id": 0, "start": 0.0, "end": 0.0, "text": text.strip(), "speaker": None}
            ]

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/original", data)
        output_uri = await storage.store(
            user_id,
            item_id,
            "output/segments.json",
            json.dumps({"segments": segments_data, "created_at": now.isoformat()}, indent=2),
        )
        await storage.store(
            user_id,
            item_id,
            "output/content.txt",
            "\n".join(segment["text"] for segment in segments_data),
        )

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
                    start_time=segment["start"],
                    end_time=segment["end"],
                    speaker=segment.get("speaker"),
                    text=segment["text"],
                )
            )
        await db.flush()

        from app.services.content_service import index_content_segments

        try:
            await index_content_segments(item_id, self.source_type, db, segments=segments_data)
        except Exception:
            logger.exception("FTS indexing failed for %s", item_id)

        logger.info("SubtitleFileAdapter: %d segments, item_id=%s", len(segments_data), item_id)
        return ContentItemResult(
            content_item_id=item_id,
            title=title,
            segment_count=len(segments_data),
        )
