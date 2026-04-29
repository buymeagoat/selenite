from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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


@runtime_checkable
class DiarizerProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...


@runtime_checkable
class OCRProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...


@runtime_checkable
class LLMProcessor(Protocol):
    key: str
    display_name: str

    def available(self) -> bool: ...
