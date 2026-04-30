from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class ASRResult:
    segments: list[TranscriptSegment]
    language: str
    duration: float


@dataclass
class DiarizedSegment:
    speaker: str
    text: str
    start: float
    end: float


@dataclass
class DiarizedResult:
    segments: list[DiarizedSegment]
    speaker_count: int


@dataclass
class ProcessorInfo:
    key: str
    display_name: str
    processor_type: str  # "asr" | "diarizer" | "ocr" | "llm"
    available: bool


@runtime_checkable
class ASRProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...
    async def transcribe(self, audio_path: Path) -> ASRResult: ...


@runtime_checkable
class DiarizerProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...
    async def diarize(self, audio_path: Path, asr_result: ASRResult) -> DiarizedResult: ...


@runtime_checkable
class OCRProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...
    async def process(self, file_path: Path) -> str: ...


@runtime_checkable
class LLMProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...
    async def run_task(self, task: str, content: str, context: dict) -> str: ...
