from app.pipeline.transcript import diarized_to_markdown
from app.processors.base import DiarizedResult, DiarizedSegment


def test_diarized_to_markdown_single_speaker():
    result = DiarizedResult(
        segments=[DiarizedSegment(speaker="Speaker 1", text="Hello world", start=0.0, end=2.0)],
        speaker_count=1,
    )
    md = diarized_to_markdown(result)
    assert md == "**Speaker 1:** Hello world"


def test_diarized_to_markdown_two_speakers():
    result = DiarizedResult(
        segments=[
            DiarizedSegment(speaker="Speaker 1", text="Hello", start=0.0, end=1.0),
            DiarizedSegment(speaker="Speaker 2", text="Hi there", start=1.5, end=3.0),
        ],
        speaker_count=2,
    )
    md = diarized_to_markdown(result)
    assert "**Speaker 1:** Hello" in md
    assert "**Speaker 2:** Hi there" in md


def test_diarized_to_markdown_empty():
    result = DiarizedResult(segments=[], speaker_count=0)
    md = diarized_to_markdown(result)
    assert md == ""
