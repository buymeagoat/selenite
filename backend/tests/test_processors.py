import pytest
from app.processors.registry import ProcessorRegistry


def test_register_and_list_asr():
    reg = ProcessorRegistry()

    class FakeASR:
        key = "fake_asr"
        display_name = "Fake ASR"
        def available(self): return True

    reg.register_asr(FakeASR())
    result = reg.list_all()
    assert len(result) == 1
    assert result[0].key == "fake_asr"
    assert result[0].processor_type == "asr"
    assert result[0].available is True


def test_unavailable_stub():
    reg = ProcessorRegistry()

    class UnavailableASR:
        key = "stub"
        display_name = "Stub"
        def available(self): return False

    reg.register_asr(UnavailableASR())
    result = reg.list_all()
    assert result[0].available is False


def test_get_by_key():
    reg = ProcessorRegistry()

    class FakeLLM:
        key = "my_llm"
        display_name = "My LLM"
        def available(self): return True

    reg.register_llm(FakeLLM())
    assert reg.get_llm("my_llm") is not None
    assert reg.get_llm("missing") is None


def test_all_four_types():
    reg = ProcessorRegistry()

    class A:
        key = "a"; display_name = "A"
        def available(self): return False
    class B:
        key = "b"; display_name = "B"
        def available(self): return False
    class C:
        key = "c"; display_name = "C"
        def available(self): return False
    class D:
        key = "d"; display_name = "D"
        def available(self): return False

    reg.register_asr(A())
    reg.register_diarizer(B())
    reg.register_ocr(C())
    reg.register_llm(D())

    types = {p.processor_type for p in reg.list_all()}
    assert types == {"asr", "diarizer", "ocr", "llm"}
