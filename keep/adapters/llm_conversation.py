"""LLM conversation import adapter.

Ports the parsing logic from app.services.llm_parser into the
ContentHub adapter pattern. Creates a ContentItem + ContentSegments
+ FTS index entry, writing metadata to the properties JSON column.
"""

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
from app.services.llm_parser import detect_provider, list_conversations, parse_conversation
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: word count * 1.33 (no tiktoken dependency)."""
    return int(len(text.split()) * 1.33)


class LlmConversationAdapter:
    """Adapter for LLM conversation exports (ChatGPT, Claude, Gemini, plain text)."""

    source_type = "llm_conversation"
    display_name = "LLM Chat Export"
    accepted_mimes = ["application/json", "text/plain", "text/markdown"]
    accepted_extensions = [".json", ".txt", ".md"]
    supported_export_formats = ["txt", "md", "json"]

    async def ingest(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        options: dict[str, Any],
        storage: StorageBackend,
    ) -> ContentItemResult:
        """Ingest an LLM conversation export.

        Required options key:
          content (str): raw export text (JSON or plain text)

        Optional options keys:
          provider (str|None): force parser — "chatgpt", "claude", "gemini", "generic"
          conversation_index (int): 0-based index for multi-conversation exports
          title (str|None): override the auto-detected title
        """
        raw = options["content"]
        provider = options.get("provider") or detect_provider(raw)
        conversation_index = int(options.get("conversation_index", 0))
        title_override = options.get("title")

        # Parse segments
        segments = parse_conversation(raw, provider=provider, conversation_index=conversation_index)

        # Derive title
        title = title_override
        if not title:
            try:
                convos = list_conversations(raw, provider=provider)
                if convos and len(convos) > conversation_index:
                    title = convos[conversation_index].get("title") or ""
            except Exception:
                pass
        if not title:
            title = f"LLM Import ({provider})"

        item_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source_uri = await storage.store(user_id, item_id, "source/input.txt", raw)

        output_data = {
            "segments": segments,
            "provider": provider,
            "created_at": now.isoformat(),
        }
        output_uri = await storage.store(
            user_id,
            item_id,
            "output/segments.json",
            json.dumps(output_data, indent=2),
        )

        lines = []
        for seg in segments:
            speaker = seg.get("speaker", "")
            text = seg.get("text", "")
            lines.append(f"{speaker}: {text}" if speaker else text)
        await storage.store(user_id, item_id, "output/content.txt", "\n".join(lines))

        item = ContentItem(
            id=item_id,
            user_id=user_id,
            adapter_type=self.source_type,
            title=title,
            source_material_path=source_uri,
            source_material_mime="text/plain",
            source_material_size=len(raw.encode("utf-8")),
            output_content_path=output_uri,
            status="ready",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        await db.flush()

        # Create ContentSegments
        for seg in segments:
            db_seg = ContentSegment(
                content_item_id=item_id,
                segment_index=seg["id"],
                start_time=float(seg.get("start", 0.0)),
                end_time=float(seg.get("end", 0.0)),
                speaker=seg.get("speaker") or None,
                text=seg["text"],
            )
            db.add(db_seg)

        # Write metadata as properties JSON
        item.properties = json.dumps(
            {
                "provider": provider,
                "conversation_index": conversation_index,
                "message_count": len(segments),
            }
        )
        item.item_type = "source"
        await db.flush()

        # Index into FTS
        from app.services.content_service import index_content_segments

        try:
            await index_content_segments(item_id, self.source_type, db, segments=segments)
        except Exception:
            logger.exception("FTS indexing failed for content item %s", item_id)
            # Non-fatal

        logger.info(
            "LlmConversationAdapter: ingested %d segments, provider=%s, item_id=%s",
            len(segments),
            provider,
            item_id,
        )
        return ContentItemResult(
            content_item_id=item_id,
            title=title,
            segment_count=len(segments),
        )
