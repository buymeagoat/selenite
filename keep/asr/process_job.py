"""End-to-end job orchestration mixin (process_job)."""

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.job import Job
from app.models.transcript import Transcript
from app.models.user_settings import UserSettings
from app.services.cloud_storage import mirror_file_to_cloud
from app.services.settings_resolver import build_effective_user_settings, get_admin_settings

logger = logging.getLogger(__name__)


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_local_bridge_uri(
    user_id: int | None,
    item_id: str,
    role: str,
    raw_path: str | None,
    fallback_filename: str,
) -> str:
    filename = Path(raw_path).name if raw_path else fallback_filename
    return f"local://{user_id}/{item_id}/{role}/{filename}"


class ProcessJobMixin:
    """Orchestrates the full transcription pipeline for a single job."""

    async def _create_audio_content_item(
        self,
        job: "Job",
        transcript_result: dict,
        db: AsyncSession,
    ) -> None:
        """Create ContentItem + ContentSegments for a completed ASR job.

        Populates item_type, job_id, properties on ContentItem and
        output_item_id, capability on Job. Non-fatal — logs warning on error.
        """
        import uuid

        from app.models.content_item import ContentItem
        from app.models.content_segment import ContentSegment

        try:
            content_item_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            title = Path(job.original_filename).stem or job.original_filename

            # Compute word count from all segment text
            all_text = " ".join(
                (seg.get("text") or "").strip() for seg in (transcript_result.get("segments") or [])
            )
            word_count = len(all_text.split()) if all_text.strip() else 0

            properties = {
                "word_count": word_count,
                "language": job.language_detected,
                "asr_model": job.model_used,
            }
            source_uri = _build_local_bridge_uri(
                job.user_id,
                content_item_id,
                "source",
                job.file_path,
                "audio",
            )
            output_uri = _build_local_bridge_uri(
                job.user_id,
                content_item_id,
                "output",
                job.transcript_path,
                "transcript.txt",
            )

            content_item = ContentItem(
                id=content_item_id,
                user_id=job.user_id,
                adapter_type="audio_transcript",
                title=title,
                item_type="artifact",
                job_id=job.id,
                source_material_path=source_uri,
                source_material_mime=job.mime_type,
                source_material_size=job.file_size,
                output_content_path=output_uri,
                properties=json.dumps(properties),
                status="ready",
                created_at=now,
                updated_at=now,
            )
            db.add(content_item)

            segments = transcript_result.get("segments") or []
            created_segments = 0
            for idx, seg in enumerate(segments):
                text_content = (seg.get("text") or "").strip()
                if not text_content:
                    continue
                db.add(
                    ContentSegment(
                        content_item_id=content_item_id,
                        segment_index=seg.get("id", idx),
                        start_time=seg.get("start") or 0.0,
                        end_time=seg.get("end") or 0.0,
                        speaker=seg.get("speaker"),
                        text=text_content,
                    )
                )
                created_segments += 1

            job.content_item_id = content_item_id  # keep for backward compat
            job.output_item_id = content_item_id
            job.capability = f"asr.{job.asr_provider_used or 'whisper'}"
            await db.commit()

            logger.info(
                "Bridge: created ContentItem %s for job %s (%d segments)",
                content_item_id,
                job.id,
                created_segments,
            )

        except Exception as exc:
            logger.warning(
                "Bridge: failed to create ContentItem for job %s (non-fatal): %s",
                job.id,
                exc,
            )
            await db.rollback()

    async def process_job(self, job_id: str, db: AsyncSession) -> None:
        """Process a transcription job end-to-end.

        Args:
            job_id: Job UUID
            db: Database session

        Updates job status, progress, and saves transcript to database.
        """
        # Late import so test monkeypatches on the whisper_service module are
        # picked up at call time (avoids the stale-reference problem).
        import app.services.whisper_service as _ws

        enforce_runtime_diarizer = _ws.enforce_runtime_diarizer
        get_asr_candidate_order = _ws.get_asr_candidate_order
        is_runtime_provider_supported = _ws.is_runtime_provider_supported
        ProviderManager = _ws.ProviderManager

        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Job not found: {job_id}")
            return

        if self._is_cancelled_state(job):
            await self._finalize_cancellation(job, db, "job fetched")
            return
        if self._is_pause_state(job):
            if job.status == "pausing":
                await self._finalize_pause(job, db, "job fetched")
            return

        settings_result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == job.user_id)
        )
        user_settings = settings_result.scalar_one_or_none()
        admin_settings = await get_admin_settings(db) if user_settings else None
        effective_settings = build_effective_user_settings(user_settings, admin_settings)
        system_preferences = await self._get_system_preferences(db)

        fast_path = settings.is_testing or settings.e2e_fast_transcription
        transcoded_path: Optional[Path] = None
        audio_path_for_processing: str = job.file_path
        try:
            if fast_path:
                await self._wait_for_processing_slot(db)
            if fast_path:
                await self._simulate_transcription(job, db)
                logger.info(f"Job {job_id} completed via simulated transcription")
                return
            # Check if already cancelled
            if self._is_cancelled_state(job):
                await self._finalize_cancellation(job, db, "before processing")
                return
            if self._is_pause_state(job):
                if job.status == "pausing":
                    await self._finalize_pause(job, db, "before processing")
                return

            runtime_diarizer = enforce_runtime_diarizer(
                requested_diarizer=job.diarizer_used,
                diarization_requested=bool(job.has_speaker_labels),
                user_settings=effective_settings,
            )
            if runtime_diarizer["notes"]:
                for note in runtime_diarizer["notes"]:
                    logger.warning("Job %s diarization adjustment: %s", job_id, note)
                # Persist diarizer runtime notes for UI transparency
                self._append_execution_notes(job, runtime_diarizer["notes"])
            job.has_speaker_labels = runtime_diarizer["diarization_enabled"]
            job.diarizer_used = runtime_diarizer["diarizer"]
            if not job.has_speaker_labels:
                job.speaker_count = None
            diarizer_record = self._resolve_diarizer_record(job.diarizer_used)
            job.diarizer_provider_used = diarizer_record.set_name if diarizer_record else None
            diarizer_ready = (
                self._diarizer_available(diarizer_record) if job.has_speaker_labels else False
            )
            if not diarizer_ready:
                if job.diarizer_used:
                    logger.warning(
                        "Job %s diarizer %s not runnable on this system; proceeding without diarization",
                        job_id,
                        job.diarizer_used,
                    )
                    self._append_execution_notes(
                        job,
                        [
                            f"Diarizer '{job.diarizer_used}' not runnable on this system; disabled speaker labels"
                        ],
                    )
                    job.diarizer_used = f"{job.diarizer_used} (failed)"
                job.has_speaker_labels = False
                job.speaker_count = 1

            # Stage 1: Loading model
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            job.progress_percent = 0
            job.progress_stage = "loading_model"
            job.estimated_total_seconds = (
                job.estimated_total_seconds or self._estimate_total_seconds(job)
            )
            job.estimated_time_left = job.estimated_total_seconds
            await db.commit()

            # Refresh in case another process marked this job failed/stalled
            await db.refresh(job)
            if job.status != "processing":
                logger.warning(
                    "Job %s left processing state during transcription; aborting finalize", job_id
                )
                return

            if await self._abort_if_cancelled(job, db, "before resolving model availability"):
                return
            if await self._abort_if_pausing(job, db, "before resolving model availability"):
                return

            # Resolve model candidates from registry (provider + entry)
            preferred_provider = job.asr_provider_used or (
                effective_settings.default_asr_provider if effective_settings else None
            )
            snapshot = ProviderManager.get_snapshot()
            enabled_asr = [
                record
                for record in snapshot["asr"]
                if record.enabled and is_runtime_provider_supported("asr", record.set_name)
            ]
            candidate_models = get_asr_candidate_order(job.model_used, effective_settings)

            def pick_records(
                names: list[str],
                preferred: Optional[str],
                *,
                requested_provider: Optional[str],
                requested_model: Optional[str],
            ):
                records = []
                seen: set[tuple[str, str]] = set()

                def push(record) -> None:
                    if not record:
                        return
                    key = (record.set_name, record.name)
                    if key in seen:
                        return
                    seen.add(key)
                    records.append(record)

                if requested_provider and requested_model:
                    push(
                        next(
                            (
                                r
                                for r in enabled_asr
                                if r.set_name == requested_provider and r.name == requested_model
                            ),
                            None,
                        )
                    )

                if requested_provider:
                    for record in enabled_asr:
                        if record.set_name == requested_provider:
                            push(record)

                for name in names:
                    pref = next(
                        (
                            r
                            for r in enabled_asr
                            if r.name == name and (preferred is None or r.set_name == preferred)
                        ),
                        None,
                    )
                    push(pref)
                    fallback = [r for r in enabled_asr if r.name == name]
                    for record in fallback:
                        push(record)
                return records

            candidate_records = pick_records(
                candidate_models,
                preferred_provider,
                requested_provider=job.asr_provider_used,
                requested_model=job.model_used,
            )
            if not candidate_records:
                raise RuntimeError("No Whisper models are available in the registry.")

            resolved_record = None
            last_error: Optional[Exception] = None
            for record in candidate_records:
                try:
                    await self._load_model_from_record(record)
                    resolved_record = record
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Job %s model '%s/%s' unavailable; trying next candidate (%s)",
                        job_id,
                        record.set_name,
                        record.name,
                        exc,
                    )
            if resolved_record is None:
                raise RuntimeError(
                    "No Whisper models are available in the configured model directory."
                ) from last_error

            logger.info(
                "Job %s using ASR model set=%s entry=%s abs_path=%s",
                job_id,
                resolved_record.set_name,
                resolved_record.name,
                resolved_record.abs_path,
            )
            if (
                resolved_record.name != job.model_used
                or resolved_record.set_name != job.asr_provider_used
            ):
                logger.warning(
                    "Job %s model/provider fallback applied: %s/%s -> %s/%s",
                    job_id,
                    job.asr_provider_used,
                    job.model_used,
                    resolved_record.set_name,
                    resolved_record.name,
                )
                self._append_execution_notes(
                    job,
                    [
                        f"ASR fallback: requested {job.asr_provider_used}/{job.model_used}"
                        f" → executed {resolved_record.set_name}/{resolved_record.name}"
                    ],
                )
                job.model_used = resolved_record.name
            job.asr_provider_used = resolved_record.set_name
            await db.commit()
            await db.refresh(job)

            model_name = resolved_record.name
            language = job.language_detected if job.language_detected != "auto" else None
            vocabulary_prompt = self._normalize_custom_vocabulary(
                getattr(effective_settings, "custom_vocabulary", None)
            )

            # Optional transcode to WAV for better backend compatibility (pyannote on CPU).
            if (
                system_preferences.transcode_to_wav
                and Path(audio_path_for_processing).suffix.lower() != ".wav"
            ):
                try:
                    transcoded_path = self._transcode_to_wav(Path(job.file_path), job.id)
                    audio_path_for_processing = str(transcoded_path)
                    logger.info("Job %s transcoded input to WAV at %s", job_id, transcoded_path)
                except Exception as exc:
                    logger.warning(
                        "Job %s failed to transcode input to WAV: %s; continuing with original file",
                        job_id,
                        exc,
                    )

            if await self._abort_if_cancelled(job, db, "after selecting model"):
                return
            if await self._abort_if_pausing(job, db, "after selecting model"):
                return

            # Stage 2: Transcribing
            job.progress_percent = 0
            job.progress_stage = "transcribing"
            job.estimated_time_left = job.estimated_time_left or job.estimated_total_seconds
            await db.commit()

            if await self._abort_if_cancelled(job, db, "before transcription"):
                return
            if await self._abort_if_pausing(job, db, "before transcription"):
                return

            # Perform transcription using the resolved record/path
            model_obj = await self._load_model_from_record(resolved_record)
            transcript_result = await self._transcribe_with_checkpoints(
                job,
                db,
                audio_path=audio_path_for_processing,
                model_name=model_name,
                language=language,
                initial_prompt=vocabulary_prompt,
                enable_timestamps=job.has_timestamps,
                model_obj=model_obj,
            )
            if transcript_result is None:
                return

            diarization_attempted = False
            if job.has_speaker_labels and diarizer_ready and diarizer_record:
                try:
                    asr_seconds, diar_seconds, total_seconds = self._estimate_stage_seconds(
                        job, duration_hint=job.duration
                    )
                    asr_weight = asr_seconds / total_seconds if total_seconds else 1.0
                    job.progress_stage = "diarizing"
                    diar_floor = int(asr_weight * 100)
                    job.progress_percent = max(int(job.progress_percent or 0), diar_floor)
                    await db.commit()
                    diar_task = asyncio.create_task(
                        self._drain_progress_during_diarization(
                            job_id,
                            start_percent=diar_floor,
                            end_percent=95,
                            expected_seconds=diar_seconds or 1.0,
                        )
                    )
                    speaker_count_hint = (
                        job.speaker_count if job.speaker_count and job.speaker_count > 1 else None
                    )
                    try:
                        diarization_result = await self._run_diarization(
                            audio_path_for_processing,
                            diarizer_record,
                            speaker_count_hint=speaker_count_hint,
                        )
                    finally:
                        diar_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await diar_task
                    job.speaker_count = diarization_result.get("speaker_count") or 1
                    diarization_segments = diarization_result.get("segments") or []
                    if diarization_segments:
                        transcript_result["segments"] = self._assign_speaker_labels(
                            transcript_result["segments"], diarization_segments
                        )
                        transcript_result["text"] = self._format_full_text(
                            transcript_result["segments"],
                            include_timestamps=job.has_timestamps,
                            include_speakers=True,
                        )
                    elif diarizer_record.set_name.lower() == "vad":
                        transcript_result["segments"] = self._apply_single_speaker_label(
                            transcript_result["segments"]
                        )
                        transcript_result["text"] = self._format_full_text(
                            transcript_result["segments"],
                            include_timestamps=job.has_timestamps,
                            include_speakers=True,
                        )
                    logger.info(
                        "Job %s diarization success using %s: %s speakers",
                        job_id,
                        diarizer_record.name,
                        job.speaker_count,
                    )
                    diar_completion = int(((asr_seconds + diar_seconds) / total_seconds) * 100)
                    diar_completion = min(max(diar_completion, diar_floor), 95)
                    job.progress_percent = max(int(job.progress_percent or 0), diar_completion)
                    diarization_attempted = True
                except Exception as exc:
                    logger.warning(
                        "Job %s diarization failed with %s: %s; falling back to 1 speaker",
                        job_id,
                        diarizer_record.name,
                        exc,
                    )
                    self._append_execution_notes(
                        job,
                        [
                            f"Diarization failed ({diarizer_record.name}): {exc}; disabled speaker labels"
                        ],
                    )
                    job.diarizer_used = f"{job.diarizer_used} (failed)"
                    job.has_speaker_labels = False
                    job.speaker_count = 1
                    diarization_attempted = True

            if diarization_attempted:
                await db.commit()

            duration = transcript_result.get("duration") or 0.0
            if duration <= 0 and job.duration:
                duration = job.duration
            if duration <= 0:
                probed = self._probe_duration_seconds(Path(audio_path_for_processing))
                if probed:
                    duration = probed
            if duration <= 0:
                duration = float(settings.default_estimated_duration_seconds)
            transcript_result["duration"] = float(duration)

            if await self._abort_if_cancelled(job, db, "after transcription"):
                return
            if await self._abort_if_pausing(job, db, "after transcription"):
                return

            # Stage 3: Finalizing
            job.progress_percent = max(int(job.progress_percent or 0), 95)
            job.progress_stage = "finalizing"
            await db.commit()

            # Save transcript to file + metadata
            transcript_path = Path(settings.transcript_storage_path) / f"{job_id}.txt"
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(transcript_result["text"], encoding="utf-8")
            metadata_path = transcript_path.with_suffix(".json")
            metadata = {
                "text": transcript_result["text"],
                "segments": transcript_result["segments"],
                "language": transcript_result["language"],
                "duration": transcript_result["duration"],
                "options": {
                    "has_timestamps": bool(job.has_timestamps),
                    "has_speaker_labels": bool(job.has_speaker_labels),
                },
            }
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            mirror_file_to_cloud(transcript_path)
            mirror_file_to_cloud(metadata_path)

            # Create transcript database record
            transcript_db = Transcript(
                job_id=job_id,
                format="txt",
                file_path=str(transcript_path),
                file_size=transcript_path.stat().st_size,
            )
            db.add(transcript_db)

            # Index segments for full-text content search
            try:
                from app.services.content_index import index_job_segments

                await index_job_segments(job_id, db, segments=transcript_result.get("segments"))
            except Exception as idx_exc:
                logger.warning(
                    "Content indexing failed for job %s (non-fatal): %s", job_id, idx_exc
                )

            # Update job with results
            started_at = _coerce_utc(job.started_at)
            if started_at:
                job.processing_seconds = int(job.processing_seconds or 0) + int(
                    (datetime.now(timezone.utc) - started_at).total_seconds()
                )
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.progress_percent = 100
            job.progress_stage = None
            job.estimated_time_left = None
            job.duration = transcript_result["duration"]
            job.language_detected = transcript_result["language"]
            if not job.speaker_count:
                job.speaker_count = self._estimate_speaker_count(transcript_result)
            job.transcript_path = str(transcript_path)
            job.estimated_total_seconds = self._estimate_total_seconds(
                job, transcript_result["duration"]
            )

            await db.commit()
            logger.info(f"Job {job_id} completed successfully")

            # Bridge: create ContentItem in universal registry (non-fatal)
            await self._create_audio_content_item(job, transcript_result, db)

            if job.checkpoint_path:
                checkpoint_path = Path(job.checkpoint_path)
                if checkpoint_path.exists():
                    with suppress(Exception):
                        checkpoint_path.unlink()
                with suppress(Exception):
                    chunk_dir = checkpoint_path.parent / "chunks"
                    if chunk_dir.exists():
                        for item in chunk_dir.glob("*.wav"):
                            item.unlink(missing_ok=True)
                        chunk_dir.rmdir()
                job.checkpoint_path = None
                await db.commit()

        except Exception as exc:
            await db.refresh(job)
            if self._is_cancelled_state(job):
                await self._finalize_cancellation(job, db, "during exception")
                return
            if self._is_pause_state(job):
                await self._finalize_pause(job, db, "during exception")
                return
            started_at = _coerce_utc(job.started_at)
            if started_at:
                job.processing_seconds = int(job.processing_seconds or 0) + int(
                    (datetime.now(timezone.utc) - started_at).total_seconds()
                )
                job.started_at = None
            logger.error(f"Job {job_id} failed: {exc}")
            job.status = "failed"
            job.progress_stage = None
            job.estimated_time_left = None
            job.error_message = str(exc)
            await db.commit()
        finally:
            if transcoded_path:
                await db.refresh(job)
                if job.status not in {"paused", "pausing"}:
                    with suppress(Exception):
                        transcoded_path.unlink(missing_ok=True)
