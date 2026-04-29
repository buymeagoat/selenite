from app.processors.base import (
    ASRProcessor, DiarizerProcessor, OCRProcessor, LLMProcessor, ProcessorInfo
)


class ProcessorRegistry:
    def __init__(self):
        self._asr: dict[str, ASRProcessor] = {}
        self._diarizer: dict[str, DiarizerProcessor] = {}
        self._ocr: dict[str, OCRProcessor] = {}
        self._llm: dict[str, LLMProcessor] = {}

    def register_asr(self, processor: ASRProcessor) -> None:
        self._asr[processor.key] = processor

    def register_diarizer(self, processor: DiarizerProcessor) -> None:
        self._diarizer[processor.key] = processor

    def register_ocr(self, processor: OCRProcessor) -> None:
        self._ocr[processor.key] = processor

    def register_llm(self, processor: LLMProcessor) -> None:
        self._llm[processor.key] = processor

    def list_all(self) -> list[ProcessorInfo]:
        result = []
        for p in self._asr.values():
            result.append(ProcessorInfo(p.key, p.display_name, "asr", p.available()))
        for p in self._diarizer.values():
            result.append(ProcessorInfo(p.key, p.display_name, "diarizer", p.available()))
        for p in self._ocr.values():
            result.append(ProcessorInfo(p.key, p.display_name, "ocr", p.available()))
        for p in self._llm.values():
            result.append(ProcessorInfo(p.key, p.display_name, "llm", p.available()))
        return result

    def get_asr(self, key: str) -> ASRProcessor | None:
        return self._asr.get(key)

    def get_diarizer(self, key: str) -> DiarizerProcessor | None:
        return self._diarizer.get(key)

    def get_ocr(self, key: str) -> OCRProcessor | None:
        return self._ocr.get(key)

    def get_llm(self, key: str) -> LLMProcessor | None:
        return self._llm.get(key)


registry = ProcessorRegistry()
