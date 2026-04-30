"""Model cache and loading mixin."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading — shared across the service
_model_cache: Dict[str, Any] = {}
_model_lock = asyncio.Lock()


class ModelLoaderMixin:
    """Load and cache ASR models for multiple providers."""

    async def load_model(self, model_name: str) -> Any:
        """Load a Whisper model, using cache if available.

        Args:
            model_name: Model size (tiny, base, small, medium, large-v3)

        Returns:
            Loaded Whisper model

        Raises:
            FileNotFoundError: If model file doesn't exist
            ImportError: If openai-whisper package not installed
        """
        async with _model_lock:
            if model_name in _model_cache:
                logger.info(f"Using cached Whisper model: {model_name}")
                return _model_cache[model_name]

            logger.info(f"Loading Whisper model: {model_name}")

            try:
                import whisper
            except ImportError:
                raise ImportError(
                    "openai-whisper package not installed. "
                    "Install with: pip install openai-whisper"
                )

            # Check if model file exists locally
            model_file = self.models_dir / f"{model_name}.pt"
            if not model_file.exists():
                raise FileNotFoundError(
                    f"Model file not found: {model_file}. "
                    f"Available models in {self.models_dir}: "
                    f"{[f.stem for f in self.models_dir.glob('*.pt')]}"
                )

            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(
                None, lambda: whisper.load_model(model_name, download_root=str(self.models_dir))
            )

            _model_cache[model_name] = model
            logger.info(f"Successfully loaded Whisper model: {model_name}")
            return model

    async def _load_model_from_record(self, record) -> Any:
        """Load an ASR backend model using the provider referenced by the record."""
        provider = (record.set_name or "").lower()
        if provider == "whisper":
            return await self._load_whisper_from_record(record)
        if provider == "faster-whisper":
            return await self._load_faster_whisper_from_record(record)
        if provider in {"transformers", "wav2vec2", "hf"}:
            return await self._load_transformers_asr_from_record(record)
        if provider in {"openai-api", "external-asr"}:
            return {"provider": "openai-api", "model_name": record.name}
        raise RuntimeError(f"Unsupported ASR provider: {provider or 'unknown'}")

    async def _load_whisper_from_record(self, record) -> Any:
        async with _model_lock:
            cache_key = f"{record.set_name}:{record.name}"
            if cache_key in _model_cache:
                return _model_cache[cache_key]
            try:
                import whisper
            except ImportError:
                raise ImportError(
                    "openai-whisper package not installed. Install with: pip install openai-whisper"
                )

            model_path = Path(record.abs_path)
            if model_path.is_file():
                download_root = model_path.parent
                model_name = model_path.stem
            elif model_path.is_dir():
                candidate = model_path / f"{record.name}.pt"
                if candidate.exists():
                    download_root = model_path
                    model_name = record.name
                else:
                    pt_files = list(model_path.glob("*.pt"))
                    if not pt_files:
                        raise FileNotFoundError(
                            f"No .pt file found in {model_path}; cannot load Whisper model {record.name}"
                        )
                    download_root = model_path
                    model_name = pt_files[0].stem
            else:
                raise FileNotFoundError(f"Model path does not exist: {model_path}")

            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(
                None, lambda: whisper.load_model(model_name, download_root=str(download_root))
            )
            wrapped = {"provider": "whisper", "model": model}
            _model_cache[cache_key] = wrapped
            return wrapped

    async def _load_faster_whisper_from_record(self, record) -> Any:
        async with _model_lock:
            cache_key = f"{record.set_name}:{record.name}"
            if cache_key in _model_cache:
                return _model_cache[cache_key]
            try:
                from faster_whisper import WhisperModel  # type: ignore
            except ImportError:
                raise ImportError(
                    "faster-whisper package not installed. Install with: pip install faster-whisper"
                )

            model_path = Path(record.abs_path)
            if model_path.is_file():
                model_path = model_path.parent
            if not model_path.exists():
                raise FileNotFoundError(f"Model path does not exist: {model_path}")

            compute_type = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "auto")
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(
                None, lambda: WhisperModel(str(model_path), compute_type=compute_type)
            )
            wrapped = {"provider": "faster-whisper", "model": model}
            _model_cache[cache_key] = wrapped
            return wrapped

    async def _load_transformers_asr_from_record(self, record) -> Any:
        async with _model_lock:
            cache_key = f"{record.set_name}:{record.name}"
            if cache_key in _model_cache:
                return _model_cache[cache_key]
            try:
                from transformers import pipeline  # type: ignore
            except ImportError:
                raise ImportError(
                    "transformers package not installed. Install with: pip install transformers"
                )

            model_ref = record.abs_path
            model_path = Path(record.abs_path)
            if model_path.exists():
                model_ref = str(model_path)
            loop = asyncio.get_event_loop()
            asr_pipeline = await loop.run_in_executor(
                None, lambda: pipeline("automatic-speech-recognition", model=model_ref)
            )
            wrapped = {"provider": "transformers", "pipeline": asr_pipeline}
            _model_cache[cache_key] = wrapped
            return wrapped
