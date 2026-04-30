"""ASR (Automatic Speech Recognition) sub-package.

Decomposes the monolithic WhisperService into focused mixins:
- FormattingMixin: text formatting, segment normalization
- EstimationMixin: processing time estimation
- JobLifecycleMixin: cancel/pause state management
- ModelLoaderMixin: model cache and loading
- TranscriptionEngineMixin: multi-engine transcription dispatch
- DiarizationMixin: speaker diarization
- CheckpointMixin: chunked transcription with checkpoints
- ProgressMixin: progress drains, simulation, slot management
- ProcessJobMixin: end-to-end job orchestration
"""
