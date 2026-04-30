"""ImportAdapter protocol and registry.

Every ingestion source type implements ImportAdapter and registers itself
at app startup via register_adapter(). New source types require no changes
to core routing, search, or viewer code.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.base import StorageBackend


@runtime_checkable
class ImportAdapter(Protocol):
    """Interface every ingestion adapter must implement."""

    # Stored in content_items.adapter_type
    source_type: str

    # Human-readable label for the Import Wizard UI
    display_name: str

    # MIME types this adapter accepts (used by wizard auto-detection)
    accepted_mimes: list[str]

    # File extensions this adapter accepts (lowercase, with leading dot)
    accepted_extensions: list[str]

    # Export formats the content type supports (drives Download menu)
    supported_export_formats: list[str]

    async def ingest(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        options: dict[str, Any],
        storage: StorageBackend,
    ) -> "ContentItemResult":
        """Ingest content and return a ContentItemResult with the created item's id."""
        ...


class ContentItemResult:
    """Result returned by an adapter's ingest() method."""

    def __init__(self, content_item_id: str, title: str, segment_count: int) -> None:
        self.content_item_id = content_item_id
        self.title = title
        self.segment_count = segment_count


# ── Registry ──────────────────────────────────────────────────────────

_registry: dict[str, ImportAdapter] = {}


def register_adapter(adapter: ImportAdapter) -> None:
    """Register an adapter. Called at app startup."""
    _registry[adapter.source_type] = adapter


def _ensure_default_adapters_registered() -> None:
    # Lazily populate defaults so CLI inspection works before FastAPI lifespan runs.
    if _registry:
        return
    from app.adapters.document_ocr import DocumentOcrAdapter
    from app.adapters.email_file import EmailAdapter
    from app.adapters.llm_conversation import LlmConversationAdapter
    from app.adapters.rich_document import RichDocumentAdapter
    from app.adapters.structured_data import StructuredDataAdapter
    from app.adapters.subtitle_file import SubtitleFileAdapter
    from app.adapters.text_file import TextFileAdapter
    from app.adapters.web_page import WebPageAdapter

    register_adapter(LlmConversationAdapter())
    register_adapter(DocumentOcrAdapter())
    register_adapter(WebPageAdapter())
    register_adapter(TextFileAdapter())
    register_adapter(StructuredDataAdapter())
    register_adapter(SubtitleFileAdapter())
    register_adapter(RichDocumentAdapter())
    register_adapter(EmailAdapter())


def get_adapter(source_type: str) -> ImportAdapter | None:
    """Return the adapter for source_type, or None if not registered."""
    _ensure_default_adapters_registered()
    return _registry.get(source_type)


def list_adapters() -> list[dict[str, Any]]:
    """Return a list of adapter descriptors for the frontend wizard."""
    _ensure_default_adapters_registered()
    return [
        {
            "source_type": a.source_type,
            "display_name": a.display_name,
            "accepted_mimes": a.accepted_mimes,
            "accepted_extensions": a.accepted_extensions,
            "supported_export_formats": a.supported_export_formats,
        }
        for a in _registry.values()
    ]


# MIMEs claimed by multiple adapters — treat as ambiguous; return None so
# the UI falls back to "Unknown file type" rather than guessing wrong.
_AMBIGUOUS_MIMES: frozenset[str] = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/json",
        "application/octet-stream",
        "text/html",
    }
)


def detect_adapter(mime: str, extension: str) -> ImportAdapter | None:
    """Return the first registered adapter that accepts this MIME type or extension.

    For non-ambiguous MIMEs, MIME matching is tried first.
    For ambiguous MIMEs (text/plain, application/json, etc.), MIME matching is
    skipped but extension matching still runs - this allows .txt, .json, .srt
    files to be correctly identified even when the detected MIME is generic.

    Extension must include the leading dot (e.g. '.pdf').
    """
    _ensure_default_adapters_registered()
    if mime not in _AMBIGUOUS_MIMES:
        for adapter in _registry.values():
            if mime in adapter.accepted_mimes:
                return adapter
    if extension:
        for adapter in _registry.values():
            if extension in adapter.accepted_extensions:
                return adapter
    return None
