"""Document OCR adapter.

Wraps the existing OCR service (app.services.ocr) to ingest image/PDF
files as ContentItems with preserved source material.
"""

from __future__ import annotations

import json
import logging
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ContentItemResult
from app.models.content_item import ContentItem
from app.models.content_segment import ContentSegment
from app.services.ocr import (
    OCRExtractionResult,
    SUPPORTED_OCR_EXTENSIONS,
    extract_text_from_bytes,
)
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

try:
    import pypdf as _pypdf  # type: ignore[import-not-found]
except ModuleNotFoundError:
    _pypdf = types.ModuleType("pypdf")

    class _MissingPdfReader:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("No module named 'pypdf'")

    _pypdf.PdfReader = _MissingPdfReader
    sys.modules.setdefault("pypdf", _pypdf)


def _split_into_paragraphs(text: str) -> list[str]:
    """Split OCR text into paragraph-sized segments on blank lines."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs if paragraphs else [text.strip()]


class DocumentOcrAdapter:
    """Adapter for OCR ingestion of images and PDFs."""

    source_type = "document_ocr"
    display_name = "Document (OCR)"
    accepted_mimes = [
        "image/png",
        "image/jpeg",
        "image/bmp",
        "image/tiff",
        "image/webp",
        "application/pdf",
    ]
    accepted_extensions = list(SUPPORTED_OCR_EXTENSIONS)
    supported_export_formats = ["txt", "md"]

    async def ingest(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        options: dict[str, Any],
        storage: StorageBackend,
    ) -> ContentItemResult:
        """Ingest a document via OCR.

        Required options key:
          upload (UploadFile): the FastAPI UploadFile object

        Optional options keys:
          language (str): OCR language code, default "eng"
          title (str|None): override title (defaults to filename)
        """
        upload = options["upload"]
        language = options.get("language", "eng")
        title_override = options.get("title")

        # Smart PDF routing: attempt text-layer extraction via pypdf first.
        # This avoids costly Tesseract OCR on digital PDFs that already have text.
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix == ".pdf":
            try:
                import io

                from pypdf import PdfReader

                raw_bytes = await upload.read()
                reader = PdfReader(io.BytesIO(raw_bytes))
                page_count = max(len(reader.pages), 1)
                extracted_pages = []
                for page in reader.pages:
                    extracted_pages.append(page.extract_text() or "")
                full_text = "\n\n".join(
                    page_text for page_text in extracted_pages if page_text.strip()
                )
                avg_chars_per_page = len(full_text) / page_count
                if avg_chars_per_page > 100:
                    await upload.seek(0)
                    title = title_override or (
                        Path(upload.filename).stem if upload.filename else "Untitled Document"
                    )
                    paragraphs = _split_into_paragraphs(full_text)
                    word_count = len(full_text.split())
                    item_id = str(uuid4())
                    now = datetime.now(timezone.utc)

                    source_uri = await storage.store(
                        user_id,
                        item_id,
                        "source/source_descriptor.json",
                        json.dumps(
                            {
                                "filename": upload.filename,
                                "byte_size": len(raw_bytes),
                                "doc_type": "pdf",
                                "note": "Text-layer extracted via pypdf.",
                            },
                            indent=2,
                        ),
                    )

                    segments_data = [
                        {"id": index, "start": 0.0, "end": 0.0, "text": paragraph, "speaker": None}
                        for index, paragraph in enumerate(paragraphs)
                    ]
                    output_data = {
                        "segments": segments_data,
                        "ocr_language": "n/a",
                        "created_at": now.isoformat(),
                    }
                    output_uri = await storage.store(
                        user_id,
                        item_id,
                        "output/segments.json",
                        json.dumps(output_data, indent=2),
                    )
                    await storage.store(user_id, item_id, "output/content.txt", full_text)

                    item = ContentItem(
                        id=item_id,
                        user_id=user_id,
                        adapter_type=self.source_type,
                        title=title,
                        source_material_path=source_uri,
                        source_material_mime="application/pdf",
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

                    item.properties = json.dumps(
                        {
                            "page_count": page_count,
                            "ocr_engine": "pypdf",
                            "word_count": word_count,
                        }
                    )
                    item.item_type = "source"
                    await db.flush()

                    from app.services.content_service import index_content_segments

                    try:
                        await index_content_segments(
                            item_id,
                            self.source_type,
                            db,
                            segments=segments_data,
                        )
                    except Exception:
                        logger.exception("FTS indexing failed for content item %s", item_id)

                    logger.info(
                        "DocumentOcrAdapter: PDF text-layer extracted via pypdf, %d paragraphs, item_id=%s",
                        len(paragraphs),
                        item_id,
                    )
                    return ContentItemResult(
                        content_item_id=item_id,
                        title=title,
                        segment_count=len(paragraphs),
                    )
                await upload.seek(0)
            except Exception:
                logger.warning(
                    "pypdf text-layer check failed; falling back to Tesseract",
                    exc_info=True,
                )
                try:
                    await upload.seek(0)
                except Exception:
                    pass

        # Save-first: read bytes, store raw file, create item with needs_processing,
        # then attempt OCR.  If OCR fails the item is preserved for retry.
        raw_bytes = await upload.read()
        filename = upload.filename or "uploaded-file"
        suffix = Path(filename).suffix.lower()
        doc_type = suffix.lstrip(".") or "unknown"
        mime = upload.content_type or "application/octet-stream"
        title = title_override or Path(filename).stem or "Untitled Document"

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Store the raw source file bytes
        source_uri = await storage.store(
            user_id,
            item_id,
            f"source/{filename}",
            raw_bytes,
        )

        # Create ContentItem immediately with needs_processing status
        item = ContentItem(
            id=item_id,
            user_id=user_id,
            adapter_type=self.source_type,
            title=title,
            source_material_path=source_uri,
            source_material_mime=mime,
            source_material_size=len(raw_bytes),
            output_content_path=None,
            status="needs_processing",
            created_at=now,
            updated_at=now,
        )
        item.item_type = "source"
        db.add(item)
        await db.flush()

        try:
            result: OCRExtractionResult = extract_text_from_bytes(raw_bytes, filename, language)

            extracted_text = result.extracted_text
            paragraphs = _split_into_paragraphs(extracted_text)
            word_count = len(extracted_text.split())

            segments_data = [
                {"id": i, "start": 0.0, "end": 0.0, "text": p, "speaker": None}
                for i, p in enumerate(paragraphs)
            ]
            output_data = {
                "segments": segments_data,
                "ocr_language": language,
                "created_at": now.isoformat(),
            }
            output_uri = await storage.store(
                user_id,
                item_id,
                "output/segments.json",
                json.dumps(output_data, indent=2),
            )
            await storage.store(user_id, item_id, "output/content.txt", extracted_text)

            item.output_content_path = output_uri
            item.status = "ready"
            item.error_message = None

            # Create ContentSegments
            for seg in segments_data:
                db.add(
                    ContentSegment(
                        content_item_id=item_id,
                        segment_index=seg["id"],
                        start_time=0.0,
                        end_time=0.0,
                        speaker=None,
                        text=seg["text"],
                    )
                )

            # Write metadata as properties JSON
            item.properties = json.dumps(
                {
                    "page_count": None,
                    "ocr_engine": "tesseract",
                    "word_count": word_count,
                }
            )
            item.item_type = "source"
            await db.flush()

            # Index into FTS
            from app.services.content_service import index_content_segments

            try:
                await index_content_segments(item_id, self.source_type, db, segments=segments_data)
            except Exception:
                logger.exception("FTS indexing failed for content item %s", item_id)

            logger.info(
                "DocumentOcrAdapter: ingested %d paragraphs, doc_type=%s, item_id=%s",
                len(paragraphs),
                doc_type,
                item_id,
            )
            segment_count = len(paragraphs)

        except Exception as exc:
            error_msg = str(exc)[:500]
            logger.warning(
                "DocumentOcrAdapter: OCR extraction failed for item_id=%s, error=%s",
                item_id,
                error_msg,
            )
            item.status = "needs_processing"
            item.error_message = error_msg
            item.properties = json.dumps(
                {
                    "page_count": None,
                    "ocr_engine": "unavailable",
                    "word_count": 0,
                }
            )
            await db.flush()
            segment_count = 0

        return ContentItemResult(
            content_item_id=item_id,
            title=title,
            segment_count=segment_count,
        )
