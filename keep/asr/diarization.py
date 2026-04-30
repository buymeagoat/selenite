"""Speaker diarization mixin."""

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class DiarizationMixin:
    """Speaker diarization: pyannote, whisperx, VAD dispatch."""

    def _resolve_diarizer_record(self, name: Optional[str]):
        if not name:
            return None
        snapshot = ProviderManager.get_snapshot()
        return next((r for r in snapshot["diarizers"] if r.name == name and r.enabled), None)

    def _diarizer_available(self, record) -> bool:
        if not record:
            return False
        provider = (record.set_name or "").lower()
        model_path = Path(record.abs_path)
        if not model_path.exists():
            logger.warning("Diarizer path missing for %s: %s", record.name, model_path)
            return False

        if provider in {"pyannote", "whisperx"}:
            config_path = model_path / "config.yaml" if model_path.is_dir() else model_path
            if not config_path.exists():
                logger.warning("Diarizer config missing for %s at %s", record.name, config_path)
                return False
            try:
                import torchaudio  # type: ignore

                if not hasattr(torchaudio, "set_audio_backend"):
                    torchaudio.set_audio_backend = lambda *args, **kwargs: None  # type: ignore[attr-defined]
                if not hasattr(torchaudio, "get_audio_backend"):
                    torchaudio.get_audio_backend = lambda *args, **kwargs: None  # type: ignore[attr-defined]
                if not hasattr(torchaudio, "list_audio_backends"):
                    torchaudio.list_audio_backends = lambda *args, **kwargs: []  # type: ignore[attr-defined]
                else:
                    try:
                        torchaudio.set_audio_backend("soundfile")  # type: ignore[attr-defined]
                    except Exception:
                        torchaudio.set_audio_backend = (
                            lambda *args, **kwargs: None
                        )  # fallback no-op
            except ImportError:
                pass
            try:
                import torch  # noqa: F401
                import pyannote.audio  # noqa: F401
            except ImportError as exc:
                logger.warning("Diarizer '%s' not available (missing deps): %s", record.name, exc)
                return False
            except Exception as exc:
                logger.warning("Diarizer '%s' import error: %s", record.name, exc)
                return False
            return True

        if provider == "vad":
            return True

        logger.warning("Diarizer provider '%s' is not supported yet", provider)
        return False

    def _collect_diarization_segments(self, diarization: Any) -> list[Dict[str, Any]]:
        """Extract diarization segments from a pyannote Annotation."""
        segments: list[Dict[str, Any]] = []
        if diarization is None:
            return segments
        try:
            iterator = diarization.itertracks(yield_label=True)
        except Exception:
            return segments
        for segment, _, label in iterator:
            start = float(getattr(segment, "start", 0.0) or 0.0)
            end = float(getattr(segment, "end", 0.0) or 0.0)
            if end <= start:
                continue
            segments.append({"start": start, "end": end, "speaker": str(label)})
        return segments

    def _assign_speaker_labels(
        self, segments: list[Dict[str, Any]], diarization_segments: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """Assign speaker labels to transcript segments by time overlap."""
        if not diarization_segments:
            return segments
        for segment in segments:
            seg_start = float(segment.get("start") or 0.0)
            seg_end = float(segment.get("end") or 0.0)
            if seg_end <= seg_start:
                continue
            best_speaker = None
            best_overlap = 0.0
            for diar in diarization_segments:
                diar_start = float(diar.get("start") or 0.0)
                diar_end = float(diar.get("end") or 0.0)
                overlap = min(seg_end, diar_end) - max(seg_start, diar_start)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = diar.get("speaker")
            if best_speaker:
                segment["speaker"] = best_speaker
        return segments

    def _apply_single_speaker_label(self, segments: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Apply a single speaker label across all transcript segments."""
        for segment in segments:
            segment["speaker"] = segment.get("speaker") or "Speaker 1"
        return segments

    async def _run_pyannote_diarization(
        self, audio_path: str, record, *, speaker_count_hint: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run pyannote diarization for a given registry record."""
        try:
            import torchaudio  # type: ignore

            if not hasattr(torchaudio, "set_audio_backend"):
                torchaudio.set_audio_backend = lambda *args, **kwargs: None  # type: ignore[attr-defined]
            if not hasattr(torchaudio, "get_audio_backend"):
                torchaudio.get_audio_backend = lambda *args, **kwargs: None  # type: ignore[attr-defined]
            if not hasattr(torchaudio, "list_audio_backends"):
                torchaudio.list_audio_backends = lambda *args, **kwargs: []  # type: ignore[attr-defined]
            else:
                try:
                    torchaudio.set_audio_backend("soundfile")  # type: ignore[attr-defined]
                except Exception:
                    torchaudio.set_audio_backend = lambda *args, **kwargs: None  # fallback no-op
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise RuntimeError(f"pyannote.audio not installed: {exc}") from exc

        model_path = Path(record.abs_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Diarizer path not found: {model_path}")

        # Allow admin to point to either a directory containing config.yaml or the config file itself.
        if model_path.is_dir():
            config_path = model_path / "config.yaml"
            base_dir = model_path
        else:
            config_path = model_path
            base_dir = model_path.parent

        if not config_path.exists():
            raise FileNotFoundError(f"Diarizer config not found at {config_path}")

        # Ensure numpy compat for pyannote
        try:
            import numpy as np  # type: ignore

            # Numpy 2.x dropped the legacy NAN alias; pyannote still references it.
            if not hasattr(np, "NAN"):
                np.NAN = np.nan  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Unable to import torch before initializing diarizer pipeline")
            raise

        # Rewrite HF repo references in config.yaml to local checkpoint files if present
        # so Pipeline/Model.from_pretrained skip hub validation and stay offline.
        def _rewrite_local_paths(obj):
            if isinstance(obj, dict):
                return {k: _rewrite_local_paths(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_rewrite_local_paths(v) for v in obj]
            if isinstance(obj, str):
                # Look for a local directory matching the repo id tail and pick a .bin inside it.
                tail = obj.split("/")[-1]
                candidate_dir = base_dir / tail
                candidate_file = candidate_dir / "pytorch_model.bin"
                if candidate_file.exists():
                    logger.info("Using local diarizer checkpoint for %s -> %s", obj, candidate_file)
                    return str(candidate_file)
                # fallback: any .bin inside the candidate dir
                if candidate_dir.is_dir():
                    bin_files = list(candidate_dir.glob("*.bin"))
                    if bin_files:
                        chosen = bin_files[0]
                        logger.info("Using local diarizer checkpoint for %s -> %s", obj, chosen)
                        return str(chosen)
            return obj

        import yaml

        with config_path.open("r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        rewritten = _rewrite_local_paths(config_data)
        local_config_path = base_dir / "_local_config.generated.yaml"
        with local_config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(rewritten, f)

        temp_wav: Optional[Path] = None

        def _load_waveform(path: Path):
            nonlocal temp_wav
            try:
                import torchaudio  # type: ignore

                waveform, sample_rate = torchaudio.load(str(path))
                return waveform, sample_rate
            except Exception as exc:
                logger.warning(
                    "Primary audio load for diarization failed (%s); attempting ffmpeg re-encode",
                    exc,
                )
                # Fallback 1: soundfile (if available) without re-encode
                try:
                    import soundfile as sf  # type: ignore
                    import torch

                    data, sample_rate = sf.read(str(path))
                    tensor = torch.tensor(data, dtype=torch.float32)
                    if tensor.ndim == 1:
                        tensor = tensor.unsqueeze(0)
                    else:
                        tensor = tensor.transpose(0, 1)
                    return tensor, sample_rate
                except Exception as sf_exc:
                    logger.warning(
                        "soundfile load also failed (%s); attempting ffmpeg re-encode", sf_exc
                    )
                try:
                    import ffmpeg  # type: ignore
                except ImportError:
                    raise RuntimeError(
                        "torchaudio/soundfile could not read diarization input and ffmpeg is missing"
                    ) from exc
                temp_wav = base_dir / f"{path.stem}-diarizer-reencode.wav"
                stream = ffmpeg.input(str(path))
                out = ffmpeg.output(
                    stream, str(temp_wav), format="wav", acodec="pcm_s16le", ar=16000, ac=1
                )
                ffmpeg.run(out, overwrite_output=True, quiet=True)
                try:
                    import soundfile as sf  # type: ignore
                    import torch

                    data, sample_rate = sf.read(str(temp_wav))
                    tensor = torch.tensor(data, dtype=torch.float32)
                    if tensor.ndim == 1:
                        tensor = tensor.unsqueeze(0)
                    else:
                        tensor = tensor.transpose(0, 1)
                    return tensor, sample_rate
                except Exception as final_exc:
                    logger.warning("Even re-encoded diarizer audio load failed (%s)", final_exc)
                    raise

        def _infer():
            import torch
            import torch.serialization as ser

            original_load = torch.load
            original_ser_load = ser.load

            def _load_weights_friendly(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return original_load(*args, **kwargs)

            def _ser_load_weights_friendly(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return original_ser_load(*args, **kwargs)

            torch.load = _load_weights_friendly  # type: ignore[assignment]
            ser.load = _ser_load_weights_friendly  # type: ignore[assignment]
            if hasattr(ser, "_set_default_weights_only"):
                try:
                    ser._set_default_weights_only(False)  # type: ignore[attr-defined]
                except Exception:
                    pass
            try:
                pipeline = Pipeline.from_pretrained(str(local_config_path))
                diarization_args: Dict[str, Any] = {}
                if speaker_count_hint is not None and speaker_count_hint >= 2:
                    diarization_args["num_speakers"] = speaker_count_hint
                try:
                    waveform, sample_rate = _load_waveform(Path(audio_path))
                    diarization = pipeline(
                        {"waveform": waveform, "sample_rate": sample_rate}, **diarization_args
                    )
                except Exception as exc:
                    logger.warning(
                        "Falling back to path-based diarization load after waveform decode failure: %s",
                        exc,
                    )
                    diarization = pipeline(audio_path, **diarization_args)
                diarization_segments = self._collect_diarization_segments(diarization)
                speakers = {seg["speaker"] for seg in diarization_segments if seg.get("speaker")}
                return {
                    "speaker_count": max(1, len(speakers)),
                    "raw": diarization,
                    "segments": diarization_segments,
                }
            finally:
                torch.load = original_load  # type: ignore[assignment]
                ser.load = original_ser_load  # type: ignore[assignment]
                if temp_wav:
                    with suppress(Exception):
                        temp_wav.unlink(missing_ok=True)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _infer)

    async def _run_vad_diarization(self, audio_path: str, record) -> Dict[str, Any]:
        """Fallback diarization that tags a single speaker when VAD is selected."""
        return {"speaker_count": 1, "segments": [], "raw": None}

    async def _run_diarization(
        self, audio_path: str, record, *, speaker_count_hint: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run diarization for the given registry record."""
        provider = (record.set_name or "").lower() if record else ""
        if provider in {"pyannote", "whisperx"}:
            if provider == "whisperx":
                logger.info("Using pyannote pipeline for whisperx diarizer provider")
            return await self._run_pyannote_diarization(
                audio_path, record, speaker_count_hint=speaker_count_hint
            )
        if provider == "vad":
            return await self._run_vad_diarization(audio_path, record)
        raise RuntimeError(f"Unsupported diarizer provider: {provider or 'unknown'}")
