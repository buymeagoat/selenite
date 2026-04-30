from app.processors.base import DiarizedResult


def diarized_to_markdown(result: DiarizedResult) -> str:
    lines = []
    for seg in result.segments:
        lines.append(f"**{seg.speaker}:** {seg.text.strip()}")
        lines.append("")
    return "\n".join(lines).strip()
