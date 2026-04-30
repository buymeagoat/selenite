"""Web Page adapter.

Fetches a URL and extracts article text via trafilatura, ingesting
the result as a ContentItem with source HTML preserved.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import trafilatura
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ContentItemResult
from app.models.content_item import ContentItem
from app.models.content_segment import ContentSegment
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_url_scheme(url: str) -> None:
    """Raise ValueError if URL scheme is not http or https."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed; use http or https")


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraph-sized segments on blank lines."""
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    return paragraphs if paragraphs else [text.strip()]


class WebPageAdapter:
    """Adapter for ingesting web pages as Content Hub items."""

    source_type = "web_page"
    display_name = "Web Page"
    accepted_mimes: list[str] = []
    accepted_extensions: list[str] = []
    supported_export_formats = ["txt"]

    async def ingest(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        options: dict[str, Any],
        storage: StorageBackend,
    ) -> ContentItemResult:
        """Ingest a web page."""
        url: str = options["url"]
        title_override: str | None = options.get("title")

        _validate_url_scheme(url)

        final_url = url
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url, headers={"User-Agent": "Selenite/1.0"})
                response.raise_for_status()
                final_url = str(response.url)
                _validate_url_scheme(final_url)
                html_content = response.text
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"HTTP {exc.response.status_code} fetching URL: {url}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Network error fetching URL: {exc}") from exc

        extracted_text: str | None = trafilatura.extract(html_content)
        if extracted_text is None:
            raise ValueError("Could not extract readable content from the URL")

        extracted_title: str | None = None
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html_content, re.IGNORECASE)
        if title_match:
            extracted_title = title_match.group(1).strip()

        title = title_override or extracted_title or final_url
        paragraphs = _split_into_paragraphs(extracted_text)
        word_count = len(extracted_text.split())

        language: str | None = None
        try:
            meta = trafilatura.extract_metadata(html_content)
            if meta and meta.language:
                language = meta.language
        except Exception:
            language = None

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/raw.html", html_content)

        segments_data = [
            {"id": index, "start": 0.0, "end": 0.0, "text": paragraph, "speaker": None}
            for index, paragraph in enumerate(paragraphs)
        ]
        output_data = {
            "segments": segments_data,
            "source_url": final_url,
            "created_at": now.isoformat(),
        }
        output_uri = await storage.store(
            user_id,
            item_id,
            "output/segments.json",
            json.dumps(output_data, indent=2),
        )
        await storage.store(user_id, item_id, "output/content.txt", extracted_text)

        item = ContentItem(
            id=item_id,
            user_id=user_id,
            adapter_type=self.source_type,
            title=title,
            source_material_path=source_uri,
            source_material_mime="text/html",
            source_material_size=len(html_content.encode("utf-8")),
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

        item.properties = json.dumps(
            {
                "source_url": final_url,
                "page_title": extracted_title,
                "word_count": word_count,
                "language": language,
            }
        )
        item.item_type = "source"
        await db.flush()

        from app.services.content_service import index_content_segments

        try:
            await index_content_segments(item_id, self.source_type, db, segments=segments_data)
        except Exception:
            logger.exception("FTS indexing failed for web page content item %s", item_id)

        logger.info(
            "WebPageAdapter: ingested %d paragraphs from %s, item_id=%s",
            len(paragraphs),
            final_url,
            item_id,
        )
        return ContentItemResult(
            content_item_id=item_id,
            title=title,
            segment_count=len(paragraphs),
        )
