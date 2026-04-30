"""Text formatting and segment normalization mixin."""

from typing import Any, Dict, Optional


class FormattingMixin:
    """Pure formatting helpers — no external state needed."""

    @staticmethod
    def _format_timecode(seconds: float) -> str:
        total_ms = max(seconds, 0.0) * 1000
        minutes, ms = divmod(int(total_ms), 60000)
        secs = (ms / 1000) % 60
        return f"{minutes:02d}:{secs:05.2f}"

    def _format_full_text(
        self,
        segments: list[Dict[str, Any]],
        *,
        include_timestamps: bool,
        include_speakers: bool,
    ) -> str:
        """Build a readable block of text honoring timestamp/speaker choices."""
        if not segments:
            return ""
        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            parts: list[str] = []
            if include_timestamps:
                parts.append(
                    f"[{self._format_timecode(seg.get('start', 0.0))} – "
                    f"{self._format_timecode(seg.get('end', 0.0))}]"
                )
            speaker = seg.get("speaker")
            if include_speakers and speaker:
                parts.append(f"{speaker}:")
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            parts.append(text)
            lines.append(" ".join(parts))
        return "\n".join(lines).strip()

    def _normalize_segments(self, segments: Optional[list]) -> list[Dict[str, Any]]:
        """Ensure every segment has id/start/end/text fields."""
        normalized: list[Dict[str, Any]] = []
        if not segments:
            return normalized

        def coerce_value(item, key, default=0.0):
            if isinstance(item, dict):
                value = item.get(key, default)
            else:
                value = getattr(item, key, default)
            return float(value or 0.0)

        def coerce_text(item):
            if isinstance(item, dict):
                raw = item.get("text") or ""
            else:
                raw = getattr(item, "text", "") or ""
            return raw.strip()

        def coerce_speaker(item):
            if isinstance(item, dict):
                return item.get("speaker")
            return getattr(item, "speaker", None)

        for idx, seg in enumerate(segments):
            text = coerce_text(seg)
            if not text:
                continue
            normalized.append(
                {
                    "id": (
                        getattr(seg, "id", idx) if not isinstance(seg, dict) else seg.get("id", idx)
                    ),
                    "start": coerce_value(seg, "start"),
                    "end": coerce_value(seg, "end"),
                    "text": text,
                    "speaker": coerce_speaker(seg),
                }
            )
        return normalized

    def _estimate_speaker_count(self, transcript_result: Dict[str, Any]) -> int:
        """Estimate number of speakers from transcript.

        Args:
            transcript_result: Transcription result dictionary

        Returns:
            Estimated speaker count
        """
        segments = transcript_result.get("segments") or []
        unique_labels: set[str] = set()
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            raw_speaker = seg.get("speaker")
            if raw_speaker is None:
                continue
            speaker = str(raw_speaker).strip()
            if speaker:
                unique_labels.add(speaker)
        if unique_labels:
            return len(unique_labels)
        return 1
