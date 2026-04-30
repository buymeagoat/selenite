from pathlib import Path
from app.processors.registry import registry
from app.processors.base import ASRResult, DiarizedResult
from app.processors.faster_whisper import FasterWhisperProcessor


class _WhisperLargeV3Stub:
    key = "whisper_large_v3"
    display_name = "Whisper Large v3"
    def available(self) -> bool: return False
    async def transcribe(self, audio_path: Path) -> ASRResult:
        raise NotImplementedError("Stub processor not available")


class _WhisperLargeV3TurboStub:
    key = "whisper_large_v3_turbo"
    display_name = "Whisper Large v3 Turbo"
    def available(self) -> bool: return False
    async def transcribe(self, audio_path: Path) -> ASRResult:
        raise NotImplementedError("Stub processor not available")


class _ParakeetStub:
    key = "parakeet_tdt_v3"
    display_name = "NVIDIA Parakeet TDT 0.6B v3"
    def available(self) -> bool: return False
    async def transcribe(self, audio_path: Path) -> ASRResult:
        raise NotImplementedError("Stub processor not available")


class _PyannoteStub:
    key = "pyannote_3_1"
    display_name = "Pyannote Speaker Diarization 3.1"
    def available(self) -> bool: return False
    async def diarize(self, audio_path: Path, asr_result: ASRResult) -> DiarizedResult:
        raise NotImplementedError("Stub processor not available")


class _MiMoStub:
    key = "mimo_v2_5_asr"
    display_name = "XiaomiMiMo MiMo-V2.5-ASR"
    def available(self) -> bool: return False
    async def diarize(self, audio_path: Path, asr_result: ASRResult) -> DiarizedResult:
        raise NotImplementedError("Stub processor not available")


class _MinerUStub:
    key = "mineru"
    display_name = "MinerU 2.5"
    def available(self) -> bool: return False
    async def process(self, file_path: Path) -> str:
        raise NotImplementedError("Stub processor not available")


class _GlmOcrStub:
    key = "glm_ocr"
    display_name = "GLM-OCR"
    def available(self) -> bool: return False
    async def process(self, file_path: Path) -> str:
        raise NotImplementedError("Stub processor not available")


class _OllamaStub:
    key = "ollama_gemma"
    display_name = "Ollama (gemma-4-e4b-it)"
    def available(self) -> bool: return False
    async def run_task(self, task: str, content: str, context: dict) -> str:
        raise NotImplementedError("Stub processor not available")


def register_all_stubs() -> None:
    registry.register_asr(_WhisperLargeV3Stub())
    registry.register_asr(_WhisperLargeV3TurboStub())
    registry.register_asr(FasterWhisperProcessor())
    registry.register_asr(_ParakeetStub())
    registry.register_diarizer(_PyannoteStub())
    registry.register_diarizer(_MiMoStub())
    registry.register_ocr(_MinerUStub())
    registry.register_ocr(_GlmOcrStub())
    registry.register_llm(_OllamaStub())
