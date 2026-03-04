import json
import os
import math
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

SUPPORTED_OUTPUT_FORMATS = {"txt", "json", "srt", "vtt"}
SUPPORTED_TASKS = {"transcribe", "translate"}
DEFAULT_TASK_NAME = "transcribe"
DEFAULT_OUTPUT_FORMAT = "txt"
TIMESTAMP_ONLY_OUTPUT_FORMATS = {"srt", "vtt"}

SUPPORTED_MODELS = ("tiny", "base", "small", "medium", "large-v3")
DEFAULT_MODEL_NAME = SUPPORTED_MODELS[-1] if SUPPORTED_MODELS else "large-v3"

MODEL_METADATA = {
    "tiny": {
        "size": "~75MB download, ~1GB in memory",
        "use_case": "Best for: Quick transcriptions, short audio, clear speech, English only",
        "selection": "- tiny: Fastest, least accurate, English only",
    },
    "base": {
        "size": "~142MB download, ~1GB in memory",
        "use_case": "Best for: General purpose, good balance of speed and accuracy",
        "selection": "- base: Good balance of speed and accuracy",
    },
    "small": {
        "size": "~466MB download, ~2GB in memory",
        "use_case": "Best for: Multiple languages, moderate accuracy needed",
        "selection": "- small: Better accuracy, supports multiple languages",
    },
    "medium": {
        "size": "~1.5GB download, ~5GB in memory",
        "use_case": "Best for: Complex audio, multiple speakers, high accuracy needed",
        "selection": "- medium: High accuracy, good for complex audio",
    },
    "large-v3": {
        "size": "~3GB download, ~10GB in memory",
        "use_case": "Best for: Professional use, maximum accuracy, complex audio",
        "selection": "- large-v3: Best accuracy, professional quality",
    },
}


def _normalize_cache_root(raw_root: str) -> Path:
    """Return a normalized cache root path with environment expansion."""
    return Path(os.path.expandvars(raw_root)).expanduser()


def get_model_cache_root() -> Path:
    """Return the base Hugging Face cache root used by faster-whisper."""
    hf_home = os.environ.get("HF_HOME")
    if hf_home and hf_home.strip():
        hf_home = hf_home.strip()
        return _normalize_cache_root(hf_home) / "hub"

    huggingface_hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if huggingface_hub_cache and huggingface_hub_cache.strip():
        huggingface_hub_cache = huggingface_hub_cache.strip()
        return _normalize_cache_root(huggingface_hub_cache)

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache and xdg_cache.strip():
        xdg_cache = xdg_cache.strip()
        return _normalize_cache_root(xdg_cache) / "huggingface" / "hub"

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data and local_app_data.strip():
            local_app_data = local_app_data.strip()
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
    except Exception as exc:  # broad catch keeps UI and CLI from crashing without context.
        message = (
            f"Unable to load Whisper model '{model_name}' with kwargs={kwargs}. "
            "This is often caused by interrupted downloads or a corrupted model cache. "
            "Try clearing your local cache and retrying, or switch models to verify model availability."
        )
        raise RuntimeError(message) from exc


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


def load_output_metadata(metadata_path: Path):
    """Load output metadata JSON if present, else return None."""
    try:
        with open(metadata_path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return None

    return payload if isinstance(payload, dict) else None


def should_skip_output_due_to_metadata(
    source_path,
    output_path,
    metadata_path,
    model_name,
    include_timestamps,
    output_format=DEFAULT_OUTPUT_FORMAT,
    task=None,
    language=None,
):
    """Return True when metadata indicates this output can be safely skipped."""
    metadata = load_output_metadata(metadata_path)
    if metadata is None:
        return False

    metadata_values = {
        "source_path": metadata.get("source_path", metadata.get("source_file")),
        "output_path": metadata.get("output_path", metadata.get("output_file")),
        "model": metadata.get("model"),
        "include_timestamps": metadata.get("include_timestamps"),
        "language": metadata.get("language"),
        "task": metadata.get("task"),
        "output_format": metadata.get("output_format", DEFAULT_OUTPUT_FORMAT),
    }

    expected = {
        "source_path": str(source_path),
        "output_path": str(output_path),
        "model": model_name,
        "include_timestamps": include_timestamps,
        "language": language,
        "task": task,
        "output_format": output_format,
    }
    if output_format in TIMESTAMP_ONLY_OUTPUT_FORMATS:
        metadata_values.pop("include_timestamps", None)
        expected.pop("include_timestamps", None)

    for key, expected_value in expected.items():
        if metadata_values.get(key) != expected_value:
            return False
    return True


def build_output_metadata_path(output_file: Path) -> Path:
    """Build the metadata sidecar path that matches output extension naming."""
    return output_file.with_suffix(f"{output_file.suffix}.metadata.json")


def resolve_output_metadata_path(output_file: Path) -> Path:
    """
    Resolve the metadata sidecar path to read, preserving legacy filenames when needed.
    """
    output_file = Path(output_file)
    preferred = build_output_metadata_path(output_file)
    legacy = output_file.with_name(f"{output_file.stem}.metadata.json")
    if preferred.exists() or not legacy.exists():
        return preferred
    return legacy
