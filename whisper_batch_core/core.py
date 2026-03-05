import math
import os
from typing import Iterable, List, Optional, Tuple

import platform
from pathlib import Path

from faster_whisper import WhisperModel

from .types import TranscriptSegment, TranscriptionResult

# All formats supported by FFmpeg that faster-whisper can extract audio from.
SUPPORTED_EXTENSIONS = {
    # Audio
    '.aac', '.aiff', '.alac', '.ape', '.flac', '.m4a', '.mp3',
    '.ogg', '.opus', '.wav', '.wma',
    # Video (audio track extracted automatically)
    '.3gp', '.avi', '.flv', '.m4v', '.mkv', '.mov', '.mp4',
    '.mpeg', '.mpg', '.ts', '.webm', '.wmv',
}

SUPPORTED_MODELS = ("tiny", "base", "small", "medium", "large-v3")
DEFAULT_MODEL_NAME = "large-v3"

SUPPORTED_TASKS = {"transcribe", "translate"}
DEFAULT_TASK_NAME = "transcribe"

SUPPORTED_OUTPUT_FORMATS = {"txt", "json", "srt", "vtt"}
DEFAULT_OUTPUT_FORMAT = "txt"
TIMESTAMP_ONLY_OUTPUT_FORMATS = {"srt", "vtt"}

MODEL_METADATA = {
    "tiny": {"size": "~75MB", "use_case": "Quick transcriptions, clear speech"},
    "base": {"size": "~142MB", "use_case": "General purpose, good speed/accuracy balance"},
    "small": {"size": "~466MB", "use_case": "Multiple languages, moderate accuracy"},
    "medium": {"size": "~1.5GB", "use_case": "Complex audio, multiple speakers"},
    "large-v3": {"size": "~3GB", "use_case": "Professional use, maximum accuracy"},
}


def _normalize_cache_root(raw_root: str) -> Path:
    """Return a normalized cache root path with environment expansion."""
    return Path(os.path.expandvars(raw_root)).expanduser()


def get_model_cache_root() -> Path:
    """Return the base Hugging Face cache root used by faster-whisper."""
    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        return _normalize_cache_root(hf_home) / "hub"

    hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE", "").strip()
    if hub_cache:
        return _normalize_cache_root(hub_cache)

    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache:
        return _normalize_cache_root(xdg_cache) / "huggingface" / "hub"

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return _normalize_cache_root(local_app_data) / "huggingface" / "hub"
        return Path.home() / "AppData" / "Local" / "huggingface" / "hub"

    return Path.home() / ".cache" / "huggingface" / "hub"


def get_model_cache_dir(model_name: str) -> Path:
    """Return expected model cache directory path for a faster-whisper model."""
    return get_model_cache_root() / f"models--Systran--faster-whisper-{model_name}"


def is_model_cached(model_name: str) -> bool:
    """Return True when the model cache path exists for the requested model."""
    return get_model_cache_dir(model_name).is_dir()


def load_model(model_name: str, device: str = "auto", compute_type: Optional[str] = None) -> WhisperModel:
    """Load a faster-whisper model with the requested device/compute settings."""
    if device == "auto" and platform.system() == "Darwin" and platform.machine() == "arm64":
        kwargs = {"device": "cpu", "compute_type": "int8"}
    else:
        kwargs = {"device": device}
    if compute_type:
        kwargs["compute_type"] = compute_type
    try:
        return WhisperModel(model_name, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load Whisper model '{model_name}' with kwargs={kwargs}. "
            "This is often caused by interrupted downloads or a corrupted model cache. "
            "Try clearing your local cache and retrying, or switch models to verify."
        ) from exc


def transcribe_segments(
    model: WhisperModel,
    audio_path: str,
    task: str = DEFAULT_TASK_NAME,
) -> Tuple[List[TranscriptSegment], object]:
    """Transcribe audio and return a list of segments plus metadata info."""
    segments, info = model.transcribe(audio_path, task=task)
    return [TranscriptSegment.from_whisper(segment) for segment in segments], info


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    try:
        total_seconds = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("Timestamp value must be a numeric type.") from exc
    if not math.isfinite(total_seconds) or total_seconds < 0:
        raise ValueError("Timestamp value must be a finite, non-negative number.")
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = int(total_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def render_timestamped_text(segments: Iterable[TranscriptSegment]) -> str:
    """Render transcript with per-segment timestamps."""
    formatted_text = []
    for segment in segments:
        start_time = format_timestamp(segment.start)
        end_time = format_timestamp(segment.end)
        text = segment.text.strip()
        formatted_text.append(f"[{start_time} --> {end_time}] {text}")
    return "\n".join(formatted_text)


def render_plain_text(segments: Iterable[TranscriptSegment]) -> str:
    """Render transcript as a single text block without timestamps."""
    text_parts = [segment.text.strip() for segment in segments]
    return " ".join(text_parts).strip()


def format_timestamp_with_millis(seconds: float, separator: str = ",") -> str:
    """Convert seconds to HH:MM:SS,mmm format for SRT/VTT."""
    total_ms = int(round(float(seconds) * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(segments: Iterable[TranscriptSegment]) -> str:
    """Render transcript in SRT subtitle format."""
    lines = []
    for index, segment in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(
            f"{format_timestamp_with_millis(segment.start, ',')} --> "
            f"{format_timestamp_with_millis(segment.end, ',')}"
        )
        lines.append((segment.text or "").strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def render_vtt(segments: Iterable[TranscriptSegment]) -> str:
    """Render transcript in WebVTT subtitle format."""
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(
            f"{format_timestamp_with_millis(segment.start, '.')} --> "
            f"{format_timestamp_with_millis(segment.end, '.')}"
        )
        lines.append((segment.text or "").strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def result_to_json_payload(segments: Iterable[TranscriptSegment]) -> dict:
    """Build a JSON-serializable transcript payload."""
    seg_list = list(segments)
    return {
        "text": " ".join((s.text or "").strip() for s in seg_list).strip(),
        "segments": [
            {"start": float(s.start), "end": float(s.end), "text": (s.text or "").strip()}
            for s in seg_list
        ],
    }


def render_output_text(
    segments: Iterable[TranscriptSegment],
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    include_timestamps: bool = True,
) -> str:
    """Render segments into the requested output format."""
    import json as _json

    if output_format == "txt":
        return render_timestamped_text(segments) if include_timestamps else render_plain_text(segments)
    if output_format == "json":
        return _json.dumps(result_to_json_payload(segments), ensure_ascii=False, indent=2)
    if output_format == "srt":
        return render_srt(segments)
    if output_format == "vtt":
        return render_vtt(segments)
    raise ValueError(f"Unsupported output format '{output_format}'.")


def transcribe_file(
    audio_path: str,
    model_name: str = DEFAULT_MODEL_NAME,
    include_timestamps: bool = True,
    device: str = "auto",
    compute_type: Optional[str] = None,
    model: Optional[WhisperModel] = None,
    task: str = DEFAULT_TASK_NAME,
) -> TranscriptionResult:
    """Transcribe a single audio file and return text plus segments metadata."""
    model = model or load_model(model_name, device=device, compute_type=compute_type)
    segments, info = transcribe_segments(model, audio_path, task=task)
    if include_timestamps:
        text = render_timestamped_text(segments)
    else:
        text = render_plain_text(segments)
    return TranscriptionResult(text=text, segments=segments, info=info)
