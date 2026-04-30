"""Structured Data adapter - ingests CSV, JSON, code, and config files."""

from __future__ import annotations

import csv
import io
import json
import logging
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

_TEXT_DECODINGS = ["utf-8", "utf-8-sig", "latin-1"]


def _decode(data: bytes) -> str:
    for enc in _TEXT_DECODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _segments_from_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [{"id": 0, "start": 0.0, "end": 0.0, "text": text, "speaker": None}]
    header = rows[0]
    segments = []
    for index, row in enumerate(rows[1:], start=0):
        line = ", ".join(f"{key}: {value}" for key, value in zip(header, row) if value.strip())
        if line:
            segments.append({"id": index, "start": 0.0, "end": 0.0, "text": line, "speaker": None})
    return segments or [{"id": 0, "start": 0.0, "end": 0.0, "text": text, "speaker": None}]


def _segments_from_jsonl(text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [
        {"id": index, "start": 0.0, "end": 0.0, "text": line, "speaker": None}
        for index, line in enumerate(lines)
    ]


def _segments_from_text(text: str) -> list[dict[str, Any]]:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        parts = [text.strip()]
    return [
        {"id": index, "start": 0.0, "end": 0.0, "text": part, "speaker": None}
        for index, part in enumerate(parts)
    ]


class StructuredDataAdapter:
    source_type = "structured_data"
    display_name = "Structured Data"
    accepted_mimes = [
        "text/csv",
        "text/tab-separated-values",
        "application/json",
        "application/x-ndjson",
        "text/x-python",
        "application/javascript",
        "text/xml",
        "application/xml",
    ]
    accepted_extensions = [
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".sh",
        ".rb",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".php",
    ]
    supported_export_formats = ["txt", "json"]

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
        filename = upload.filename or "data"
        ext = Path(filename).suffix.lower()
        title = (
            title_override
            or Path(filename).stem.replace("_", " ").replace("-", " ").strip()
            or filename
        )

        if ext in (".csv", ".tsv"):
            segments_data = _segments_from_csv(text)
        elif ext == ".jsonl":
            segments_data = _segments_from_jsonl(text)
        else:
            segments_data = _segments_from_text(text)

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/original", data)
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
            source_material_mime=upload.content_type or "application/octet-stream",
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

        logger.info(
            "StructuredDataAdapter: %d segments, ext=%s, item_id=%s",
            len(segments_data),
            ext,
            item_id,
        )
        return ContentItemResult(
            content_item_id=item_id,
            title=title,
            segment_count=len(segments_data),
        )
