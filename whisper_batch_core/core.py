import json
import os
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Tuple, Union

import platform

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

SUPPORTED_TASKS = ("transcribe", "translate")
DEFAULT_TASK_NAME = "transcribe"

SUPPORTED_OUTPUT_FORMATS = {"txt", "json", "srt", "vtt"}
DEFAULT_OUTPUT_FORMAT = "txt"
TIMESTAMP_ONLY_OUTPUT_FORMATS = {"srt", "vtt"}

MODEL_METADATA: Mapping[str, Mapping[str, str]] = {
    "tiny": {
        "size": "0.1 GB",
        "use_case": "Fastest startup; rough transcriptions.",
        "selection": "- tiny: highest speed, lower quality",
    },
    "base": {
        "size": "0.4 GB",
        "use_case": "Balanced speed and quality for most tasks.",
        "selection": "- base: good default balance.",
    },
    "small": {
        "size": "1.0 GB",
        "use_case": "Higher quality than base, still fast.",
        "selection": "- small: improved transcription quality.",
    },
    "medium": {
        "size": "2.9 GB",
        "use_case": "Higher quality and punctuation.",
        "selection": "- medium: stronger accuracy for long-form audio.",
    },
    "large-v3": {
        "size": "6.0 GB",
        "use_case": "Best quality and strongest long-form accuracy.",
        "selection": "- large-v3: highest accuracy, longest runtime.",
    },
}


def load_model(model_name: str, device: str = "auto", compute_type: Optional[str] = None) -> WhisperModel:
    """Load a faster-whisper model with the requested device/compute settings."""
    if device == "auto" and platform.system() == "Darwin" and platform.machine() == "arm64":
        kwargs = {"device": "cpu", "compute_type": "int8"}
    else:
        kwargs = {"device": device}
    if compute_type:
        kwargs["compute_type"] = compute_type
    return WhisperModel(model_name, **kwargs)


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
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
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
    task: str = DEFAULT_TASK_NAME
) -> TranscriptionResult:
    """Transcribe a single audio file and return text plus segments metadata."""
    model = model or load_model(model_name, device=device, compute_type=compute_type)
    segments, info = transcribe_segments(model, audio_path, task=task)
    if include_timestamps:
        text = render_timestamped_text(segments)
    else:
        text = render_plain_text(segments)
    return TranscriptionResult(text=text, segments=segments, info=info)


def get_model_cache_dir(model_name: str, *, cache_dir: Optional[str] = None) -> Path:
    """Return the cached model directory path used by faster-whisper."""
    model_key = model_name.strip()
    hf_dir = Path(cache_dir).expanduser() if cache_dir else _resolve_hf_cache_root()
    return hf_dir / f"models--Systran--faster-whisper-{model_key}"


def _resolve_hf_cache_root() -> Path:
    """Resolve Hugging Face cache root using env var precedence."""
    hf_home = os.getenv("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "hub"

    hf_cache = os.getenv("HUGGINGFACE_HUB_CACHE")
    if hf_cache:
        return Path(hf_cache).expanduser()

    xdg_cache = os.getenv("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "huggingface" / "hub"

    return Path.home() / ".cache" / "huggingface" / "hub"


def is_model_cached(model_name: str, *, cache_dir: Optional[str] = None) -> bool:
    """Return True when the given model cache directory exists."""
    return get_model_cache_dir(model_name, cache_dir=cache_dir).is_dir()


def _metadata_suffix_path(output_path: Union[str, Path]) -> Path:
    output_path_obj = Path(output_path)
    return output_path_obj.with_name(f"{output_path_obj.name}.metadata.json")


def build_output_metadata_path(output_path: Union[str, Path]) -> Path:
    """Return the metadata sidecar path for an output file."""
    return _metadata_suffix_path(output_path)


def resolve_output_metadata_path(output_path: Union[str, Path]) -> Path:
    """Return the metadata sidecar path to read for an output file."""
    return _metadata_suffix_path(output_path)


def should_skip_output_due_to_metadata(
    *,
    source_path: str,
    output_path: str,
    metadata_path: Union[str, Path],
    model_name: str,
    include_timestamps: bool,
    output_format: str,
    task: str = DEFAULT_TASK_NAME,
) -> bool:
    """Return True when metadata proves this output is up-to-date for current run settings."""
    try:
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False

    expected = {
        "source_path": str(source_path),
        "output_path": str(output_path),
        "model": model_name,
        "include_timestamps": bool(include_timestamps),
        "output_format": output_format,
        "task": task,
    }
    return all(metadata.get(key) == value for key, value in expected.items())
