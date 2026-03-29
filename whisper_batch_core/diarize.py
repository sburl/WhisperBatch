"""Optional speaker diarization using pyannote.audio.

All pyannote imports are lazy so the base package works without pyannote installed.
"""

import os
from typing import List, Optional

from .types import TranscriptSegment


def _check_pyannote_available() -> None:
    """Raise a clear error if pyannote.audio is not installed."""
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "Speaker diarization requires pyannote.audio.\n"
            "Install it with:  pip install 'whisper-batch-core[diarize]'\n"
            "Then obtain a HuggingFace token at https://huggingface.co/settings/tokens\n"
            "and accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1"
        )


def load_diarization_pipeline(hf_token: str):
    """Load the pyannote speaker-diarization pipeline.

    The returned pipeline object is reusable across multiple audio files.
    """
    _check_pyannote_available()
    from pyannote.audio import Pipeline

    return Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )


def run_diarization(pipeline, audio_path: str):
    """Run the diarization pipeline on an audio file and return the annotation."""
    return pipeline(audio_path)


def assign_speakers(
    segments: List[TranscriptSegment],
    annotation,
) -> List[TranscriptSegment]:
    """Assign speaker labels to transcript segments based on time overlap.

    For each segment the speaker whose turn has the greatest overlap is chosen.
    Segments with no overlapping speaker turn are labelled ``"Unknown"``.
    """
    if not segments:
        return []

    # Pre-collect speaker turns for efficient iteration
    turns = [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]

    # Normalise raw pyannote labels (e.g. "SPEAKER_00") into friendly names
    unique_speakers = sorted(set(spk for _, _, spk in turns))
    label_map = {raw: f"Speaker {i + 1}" for i, raw in enumerate(unique_speakers)}

    result: List[TranscriptSegment] = []
    for seg in segments:
        best_speaker: Optional[str] = None
        best_overlap = 0.0
        for t_start, t_end, raw_label in turns:
            overlap = max(0.0, min(seg.end, t_end) - max(seg.start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = label_map[raw_label]
        result.append(seg.with_speaker(best_speaker or "Unknown"))
    return result


def diarize_segments(
    segments: List[TranscriptSegment],
    audio_path: str,
    hf_token: str,
    pipeline=None,
) -> List[TranscriptSegment]:
    """Convenience wrapper: load pipeline (if needed), diarize, and assign speakers."""
    if not hf_token:
        hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        raise ValueError(
            "A HuggingFace token is required for speaker diarization. "
            "Pass --hf-token or set the HF_TOKEN environment variable."
        )
    if pipeline is None:
        pipeline = load_diarization_pipeline(hf_token)
    annotation = run_diarization(pipeline, audio_path)
    return assign_speakers(segments, annotation)
