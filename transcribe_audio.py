#!/usr/bin/env python3

import argparse
import csv
import importlib
import shlex
import zipfile
import json
import time
import subprocess
import sys
from collections import Counter
from pathlib import Path

from whisper_batch_core import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_MODELS,
    SUPPORTED_TASKS,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TASK_NAME,
    DEFAULT_MODEL_NAME,
    MODEL_METADATA,
    get_model_cache_dir,
    is_model_cached,
    build_output_metadata_path,
    resolve_output_metadata_path,
    should_skip_output_due_to_metadata,
    load_model,
    transcribe_file,
)
from whisper_batch_core.async_batch import (
    build_stable_task_queue,
    evaluate_async_execution_policy,
)
SUPPORTED_PYTHON_MINIMUM = (3, 9)
SUPPORTED_PYTHON_MAXIMUM = (3, 13)
POSTMORTEM_LOG_PATH = "postmortem.jsonl"
SUPPORTED_PROFILE_OPTIONS = {
    "model",
    "include_timestamps",
    "retries",
    "retry_delay",
    "retry_backoff",
    "export_bundle",
    "language",
    "task",
    "postprocess_command",
    "postprocess_plugin",
    "output_format",
    "max_workers",
    "overwrite",
    "resume",
}
CONFIG_FILENAME = ".whisperbatch"
DEFAULT_CLI_OPTIONS = {
    "model_name": DEFAULT_MODEL_NAME,
    "include_timestamps": True,
    "max_workers": 1,
    "resume": False,
    "overwrite": False,
    "retries": 0,
    "retry_delay": 1.0,
    "retry_backoff": 2.0,
    "export_bundle": None,
    "language": None,
    "task": DEFAULT_TASK_NAME,
    "postprocess_command": None,
    "postprocess_plugin": None,
    "output_format": DEFAULT_OUTPUT_FORMAT,
    "language_profiles": None,
    "language_profile": None,
    "speaker_profiles": None,
    "speaker_profile": None,
    "annotation_export": None,
}
TIMESTAMP_ONLY_OUTPUT_FORMATS = {"srt", "vtt"}

def _validate_runtime_python_version() -> None:
    version = sys.version_info[:2]
    if version < SUPPORTED_PYTHON_MINIMUM:
        minimum = f"{SUPPORTED_PYTHON_MINIMUM[0]}.{SUPPORTED_PYTHON_MINIMUM[1]}"
        current = f"{version[0]}.{version[1]}"
        raise RuntimeError(
            f"Unsupported Python version {current}; this tool supports Python "
            f"{minimum}+ up to 3.13."
        )
    if version > SUPPORTED_PYTHON_MAXIMUM:
        maximum = f"{SUPPORTED_PYTHON_MAXIMUM[0]}.{SUPPORTED_PYTHON_MAXIMUM[1]}"
        current = f"{version[0]}.{version[1]}"
        raise RuntimeError(
            f"Unsupported Python version {current}; this tool currently validates "
            f"only up to Python {maximum}."
        )


def _path_sort_key(path: Path) -> tuple[str, str]:
    """Sort key helper with deterministic case-variant tie-breaker."""
    path_text = str(path)
    return path_text.lower(), path_text


def _load_model_with_status(model_name: str):
    """Load a model with explicit cache/download status logs."""
    cache_dir = get_model_cache_dir(model_name)
    model_is_cached = is_model_cached(model_name)
    model_size = MODEL_METADATA.get(model_name, {}).get("size")
    if model_is_cached:
        size_hint = f" ({model_size})" if model_size else ""
        print(f"Found cached model '{model_name}' at {cache_dir}{size_hint}.")
    else:
        size_hint = f" ({model_size})" if model_size else ""
        print(
            f"Model '{model_name}' not cached locally yet{size_hint}. "
            f"It will be downloaded on first use to {cache_dir}."
        )

    start_time = time.perf_counter()
    model = load_model(model_name, device="auto")
    elapsed = time.perf_counter() - start_time
    if model_is_cached:
        print(f"Model '{model_name}' loaded from cache in {elapsed:.2f}s.")
    else:
        print(f"Model '{model_name}' download/load finished in {elapsed:.2f}s.")
    return model


def _build_output_file_path(output_dir: Path, source_path: Path, output_format: str, occurrence: int = 1) -> Path:
    """Build an output path, adding a collision-safe suffix when needed."""
    base_name = f"{source_path.stem}_transcription"
    if occurrence > 1:
        base_name = f"{base_name}_{occurrence}"
    return output_dir / f"{base_name}.{output_format}"


SUPPORTED_CONFIG_KEYS = {
    "model",
    "include_timestamps",
    "timestamps",
    "resume",
    "overwrite",
    "retries",
    "retry_delay",
    "retry_backoff",
    "max_workers",
    "export_bundle",
    "language",
    "task",
    "postprocess_command",
    "postprocess_plugin",
    "output_format",
    "language_profiles",
    "language_profile",
    "speaker_profiles",
    "speaker_profile",
    "annotation_export",
}


def _format_timestamp_with_millis(seconds, separator=","):
    total_milliseconds = int(round(float(seconds) * 1000))
    hours = total_milliseconds // 3600000
    minutes = (total_milliseconds % 3600000) // 60000
    secs = ((total_milliseconds % 60000) // 1000)
    millis = total_milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _render_srt(segments):
    output_lines = []
    for i, segment in enumerate(segments, 1):
        output_lines.append(str(i))
        output_lines.append(
            f"{_format_timestamp_with_millis(segment.start, ',')} --> "
            f"{_format_timestamp_with_millis(segment.end, ',')}"
        )
        output_lines.append((segment.text or "").strip())
        output_lines.append("")

    return "\n".join(output_lines).rstrip()


def _render_vtt(segments):
    output_lines = ["WEBVTT", ""]
    for segment in segments:
        output_lines.append(
            f"{_format_timestamp_with_millis(segment.start, '.')} --> {_format_timestamp_with_millis(segment.end, '.')}"
        )
        output_lines.append((segment.text or "").strip())
        output_lines.append("")

    return "\n".join(output_lines).rstrip()


def _render_output_text(result, output_format: str) -> str:
    if output_format == DEFAULT_OUTPUT_FORMAT:
        return result.text
    if output_format == "json":
        return json.dumps(_result_to_json_payload(result), ensure_ascii=False, indent=2)
    if output_format == "srt":
        return _render_srt(result.segments)
    if output_format == "vtt":
        return _render_vtt(result.segments)
    raise ValueError(f"Unsupported output format '{output_format}'.")


def _effective_include_timestamps_for_output(output_format: str, include_timestamps: bool) -> bool:
    if output_format in TIMESTAMP_ONLY_OUTPUT_FORMATS:
        return False
    return bool(include_timestamps)


def _result_to_json_payload(result):
    return {
        "text": result.text,
        "segments": [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            for segment in result.segments
        ],
    }


def _validate_cli_args(
    directory_path,
    model_name,
    retries,
    retry_delay,
    retry_backoff=1.0,
    max_workers=1,
    export_bundle=None,
    language=None,
    postprocess_command=None,
    postprocess_plugin=None,
    output_format=DEFAULT_OUTPUT_FORMAT,
    task=DEFAULT_TASK_NAME,
    include_timestamps=True,
    resume=False,
    annotation_export=None,
):
    if not directory_path:
        raise ValueError("Directory path is required and cannot be empty.")

    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model '{model_name}'. Supported values are: {', '.join(sorted(SUPPORTED_MODELS))}.")

    if not isinstance(retries, int) or retries < 0:
        raise ValueError("--retries must be an integer greater than or equal to 0.")

    if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
        raise ValueError("--retry-delay must be greater than or equal to 0.")

    if not isinstance(retry_backoff, (int, float)) or retry_backoff <= 0:
        raise ValueError("--retry-backoff must be greater than 0.")

    if not isinstance(max_workers, int) or max_workers < 1:
        raise ValueError("--max-workers must be an integer greater than or equal to 1.")

    if export_bundle is not None and (
        not isinstance(export_bundle, (str, Path))
        or not str(export_bundle).strip()
    ):
        raise ValueError("--export-bundle must be a non-empty string.")

    if language is not None and (not isinstance(language, str) or not language.strip()):
        raise ValueError("--language must be a non-empty string.")

    if postprocess_command is not None and (
        not isinstance(postprocess_command, str) or not postprocess_command.strip()
    ):
        raise ValueError("--postprocess-cmd must be a non-empty string.")

    if postprocess_plugin is not None:
        if not isinstance(postprocess_plugin, str):
            raise ValueError(
                "--postprocess-plugin must be in the format <module>:<callable> and non-empty."
            )
        postprocess_plugin = postprocess_plugin.strip()
        if not postprocess_plugin or ":" not in postprocess_plugin:
            raise ValueError(
                "--postprocess-plugin must be in the format <module>:<callable> and non-empty."
            )

    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(
            "Unsupported output format '{0}'. Supported values are: {1}.".format(
                output_format, ", ".join(sorted(SUPPORTED_OUTPUT_FORMATS))
            )
        )

    if task not in SUPPORTED_TASKS:
        raise ValueError(
            "Unsupported task '{0}'. Supported values are: {1}.".format(
                task, ", ".join(sorted(SUPPORTED_TASKS))
            )
        )

    if not isinstance(include_timestamps, bool):
        raise ValueError("--timestamps must resolve to a boolean.")

    if not isinstance(resume, bool):
        raise ValueError("--resume must resolve to a boolean.")

    if annotation_export is not None:
        if not isinstance(annotation_export, (str, Path)) or not str(annotation_export).strip():
            raise ValueError("--annotation-export must be a non-empty string.")
        annotation_export_path = Path(annotation_export)
        suffix = annotation_export_path.suffix.lower()
        if suffix and suffix not in {".csv", ".jsonl"}:
            raise ValueError("--annotation-export must end with .csv or .jsonl.")


def _write_output_metadata(
    metadata_path: Path,
    source_path: Path,
    output_path: Path,
    model_name: str,
    include_timestamps: bool,
    language: str,
    task: str,
    overwrite: bool,
    retries: int,
    retry_delay: float,
    retry_backoff: float,
    output_format: str,
):
    payload = {
        "source_path": str(source_path),
        "output_path": str(output_path),
        "model": model_name,
        "include_timestamps": include_timestamps,
        "language": language,
        "task": task,
        "overwrite": overwrite,
        "retries": retries,
        "retry_delay": retry_delay,
        "retry_backoff": retry_backoff,
        "output_format": output_format,
        "processed_at": time.time(),
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _normalize_export_bundle_path(directory_path, export_bundle):
    bundle_path = Path(export_bundle)
    if not bundle_path.suffix:
        bundle_path = bundle_path.with_suffix(".zip")
    if not bundle_path.is_absolute():
        bundle_path = Path(directory_path) / bundle_path
    return bundle_path


def _normalize_annotation_export_path(directory_path, annotation_export):
    export_path = Path(annotation_export)
    if not export_path.suffix:
        export_path = export_path.with_suffix(".csv")
    if not export_path.is_absolute():
        export_path = Path(directory_path) / export_path
    return export_path


def _annotation_export_rows(source_path: Path, output_file: Path, result, metadata: dict):
    rows = []
    for index, segment in enumerate(result.segments, start=1):
        rows.append(
            {
                "source_path": str(source_path),
                "output_path": str(output_file),
                "segment_index": index,
                "start_seconds": float(segment.start),
                "end_seconds": float(segment.end),
                "text": (segment.text or "").strip(),
                "model": metadata["model"],
                "include_timestamps": metadata["include_timestamps"],
                "language": metadata["language"],
                "task": metadata["task"],
                "output_format": metadata["output_format"],
            }
        )
    return rows


def _write_annotation_export(annotation_export_path: Path, rows: list[dict]):
    annotation_export_path.parent.mkdir(parents=True, exist_ok=True)
    rows_sorted = sorted(rows, key=lambda row: (row["source_path"], row["segment_index"]))
    fieldnames = [
        "source_path",
        "output_path",
        "segment_index",
        "start_seconds",
        "end_seconds",
        "text",
        "model",
        "include_timestamps",
        "language",
        "task",
        "output_format",
    ]

    if annotation_export_path.suffix.lower() == ".jsonl":
        with open(annotation_export_path, "w", encoding="utf-8") as export_file:
            for row in rows_sorted:
                export_file.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")
        return

    with open(annotation_export_path, "w", encoding="utf-8", newline="") as export_file:
        writer = csv.DictWriter(export_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(row)


def _export_bundle(bundle_path, directory_path, summary):
    output_dir = Path(directory_path) / "transcriptions"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_payload = dict(summary)
    bundle_payload["export_bundle"] = str(bundle_path)

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
        if output_dir.exists():
            for path in sorted(output_dir.rglob("*"), key=_path_sort_key):
                if path.is_file():
                    archive.write(path, arcname=str(path.relative_to(directory_path)))
        archive.writestr("run_summary.json", json.dumps(bundle_payload, ensure_ascii=False, indent=2))


def _normalize_config_value_map(raw_config):
    normalized = {}
    for key, value in raw_config.items():
        if key == "timestamps":
            key = "include_timestamps"

        if key not in SUPPORTED_CONFIG_KEYS:
            raise ValueError(f"Unsupported config key '{key}' in {CONFIG_FILENAME}.")

        if key in normalized:
            raise ValueError(f"Duplicate config key '{key}' in {CONFIG_FILENAME}.")

        normalized[key] = value

    return normalized


def _normalize_profile_value_map(profile, name, profile_kind):
    normalized = {}
    for key, value in profile.items():
        if key == "timestamps":
            key = "include_timestamps"
        if key == "model":
            key = "model_name"

        if key not in SUPPORTED_PROFILE_OPTIONS:
            raise ValueError(
                f"Unsupported option '{key}' in {profile_kind} profile '{name}' in {CONFIG_FILENAME}."
            )

        if key in normalized:
            raise ValueError(
                f"Duplicate option '{key}' in {profile_kind} profile '{name}' in {CONFIG_FILENAME}."
            )

        normalized[key] = value

    return normalized


def _normalize_profiles(raw_profiles, profile_kind):
    if raw_profiles is None:
        return None

    if not isinstance(raw_profiles, dict):
        raise ValueError(f"{profile_kind}_profiles in {CONFIG_FILENAME} must be an object.")

    normalized = {}
    for name, profile in raw_profiles.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{profile_kind} profile names in {CONFIG_FILENAME} must be non-empty strings.")
        if not isinstance(profile, dict):
            raise ValueError(
                f"{profile_kind} profile '{name}' in {CONFIG_FILENAME} must be an object."
            )
        normalized[name] = _normalize_profile_value_map(profile, name, profile_kind)

    return normalized


def _apply_profile_selection(
    merged,
    profiles,
    selected_name,
    profile_kind,
    profiles_map_label,
):
    if selected_name is None:
        return

    if not isinstance(selected_name, str) or not selected_name.strip():
        raise ValueError(f"{profile_kind} profile name must be a non-empty string.")

    if profiles is None:
        raise ValueError(f"{profile_kind} profile '{selected_name}' requires {profiles_map_label} in {CONFIG_FILENAME}.")

    if selected_name not in profiles:
        raise ValueError(f"Unknown {profile_kind} profile '{selected_name}' in {CONFIG_FILENAME}.")

    merged.update(profiles[selected_name])


def _load_config_file(directory_path, config_path=None):
    if config_path is None:
        candidate = Path(directory_path) / CONFIG_FILENAME
        if not candidate.exists():
            return {}
        config_path = candidate
    else:
        config_path = Path(config_path)

    try:
        with open(config_path, "r", encoding="utf-8") as file_obj:
            raw_config = json.load(file_obj)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {config_path}: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read config file {config_path}: {exc.strerror}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError(f"Invalid config format in {config_path}: expected a JSON object.")

    normalized = _normalize_config_value_map(raw_config)
    language_profiles = _normalize_profiles(normalized.get("language_profiles"), "language")
    speaker_profiles = _normalize_profiles(normalized.get("speaker_profiles"), "speaker")

    return {
        "model_name": normalized.get("model"),
        "include_timestamps": normalized.get("include_timestamps"),
        "resume": normalized.get("resume"),
        "overwrite": normalized.get("overwrite"),
        "retries": normalized.get("retries"),
        "retry_delay": normalized.get("retry_delay"),
        "retry_backoff": normalized.get("retry_backoff"),
        "max_workers": normalized.get("max_workers"),
        "export_bundle": normalized.get("export_bundle"),
        "language": normalized.get("language"),
        "task": normalized.get("task"),
        "postprocess_command": normalized.get("postprocess_command"),
        "postprocess_plugin": normalized.get("postprocess_plugin"),
        "output_format": normalized.get("output_format"),
        "language_profiles": language_profiles,
        "language_profile": normalized.get("language_profile"),
        "speaker_profiles": speaker_profiles,
        "speaker_profile": normalized.get("speaker_profile"),
        "annotation_export": normalized.get("annotation_export"),
    }


def _resolve_options(directory_path, args):
    """Resolve CLI options by merging .whisperbatch config with explicit CLI args."""
    config = _load_config_file(directory_path, config_path=getattr(args, "config_path", None))

    merged = dict(DEFAULT_CLI_OPTIONS)
    if config.get("model_name") is not None:
        merged["model_name"] = config["model_name"]
    if config.get("include_timestamps") is not None:
        merged["include_timestamps"] = config["include_timestamps"]
    if config.get("resume") is not None:
        merged["resume"] = config["resume"]
    if config.get("overwrite") is not None:
        merged["overwrite"] = config["overwrite"]
    if config.get("retries") is not None:
        merged["retries"] = config["retries"]
    if config.get("retry_delay") is not None:
        merged["retry_delay"] = config["retry_delay"]
    if config.get("retry_backoff") is not None:
        merged["retry_backoff"] = config["retry_backoff"]
    if config.get("output_format") is not None:
        merged["output_format"] = config["output_format"]
    if config.get("postprocess_command") is not None:
        merged["postprocess_command"] = config["postprocess_command"]
    if config.get("postprocess_plugin") is not None:
        plugin_spec = config["postprocess_plugin"]
        merged["postprocess_plugin"] = plugin_spec.strip() if isinstance(plugin_spec, str) else plugin_spec
    if config.get("max_workers") is not None:
        merged["max_workers"] = config["max_workers"]
    if config.get("export_bundle") is not None:
        merged["export_bundle"] = config["export_bundle"]
    if config.get("language") is not None:
        merged["language"] = config["language"]
    if config.get("task") is not None:
        merged["task"] = config["task"]
    if config.get("language_profiles") is not None:
        merged["language_profiles"] = config["language_profiles"]
    if config.get("language_profile") is not None:
        merged["language_profile"] = config["language_profile"]
    if config.get("speaker_profiles") is not None:
        merged["speaker_profiles"] = config["speaker_profiles"]
    if config.get("speaker_profile") is not None:
        merged["speaker_profile"] = config["speaker_profile"]
    if config.get("annotation_export") is not None:
        merged["annotation_export"] = config["annotation_export"]

    _apply_profile_selection(
        merged=merged,
        profiles=config.get("language_profiles"),
        selected_name=config.get("language_profile"),
        profile_kind="Language",
        profiles_map_label="language_profiles",
    )
    _apply_profile_selection(
        merged=merged,
        profiles=config.get("speaker_profiles"),
        selected_name=config.get("speaker_profile"),
        profile_kind="Speaker",
        profiles_map_label="speaker_profiles",
    )

    if args.model is not None:
        merged["model_name"] = args.model
    if args.include_timestamps is not None:
        merged["include_timestamps"] = args.include_timestamps
    if args.overwrite is not None:
        merged["overwrite"] = args.overwrite
    if args.retries is not None:
        merged["retries"] = args.retries
    if args.retry_delay is not None:
        merged["retry_delay"] = args.retry_delay
    if args.retry_backoff is not None:
        merged["retry_backoff"] = args.retry_backoff
    if args.output_format is not None:
        merged["output_format"] = args.output_format
    if args.postprocess_command is not None:
        merged["postprocess_command"] = args.postprocess_command
    if args.postprocess_plugin is not None:
        merged["postprocess_plugin"] = args.postprocess_plugin.strip()
    if args.max_workers is not None:
        merged["max_workers"] = args.max_workers
    if args.export_bundle is not None:
        merged["export_bundle"] = args.export_bundle
    if args.language is not None:
        merged["language"] = args.language
    if args.task is not None:
        merged["task"] = args.task
    if args.annotation_export is not None:
        merged["annotation_export"] = args.annotation_export
    if args.language_profile is not None:
        _apply_profile_selection(
            merged=merged,
            profiles=merged.get("language_profiles"),
            selected_name=args.language_profile,
            profile_kind="Language",
            profiles_map_label="language_profiles",
        )
        merged["language_profile"] = args.language_profile
    if args.speaker_profile is not None:
        _apply_profile_selection(
            merged=merged,
            profiles=merged.get("speaker_profiles"),
            selected_name=args.speaker_profile,
            profile_kind="Speaker",
            profiles_map_label="speaker_profiles",
        )
        merged["speaker_profile"] = args.speaker_profile
    if args.resume is not None:
        merged["resume"] = args.resume

    _validate_cli_args(
        directory_path=directory_path,
        model_name=merged["model_name"],
        retries=merged["retries"],
        retry_delay=merged["retry_delay"],
        retry_backoff=merged["retry_backoff"],
        max_workers=merged["max_workers"],
        export_bundle=merged["export_bundle"],
        language=merged["language"],
        task=merged["task"],
        postprocess_command=merged["postprocess_command"],
        output_format=merged["output_format"],
        postprocess_plugin=merged["postprocess_plugin"],
        include_timestamps=merged["include_timestamps"],
        resume=merged["resume"],
        annotation_export=merged["annotation_export"],
    )

    return merged


def transcribe_audio(
    file_path,
    model_name=DEFAULT_MODEL_NAME,
    include_timestamps=True,
    language=None,
    task=DEFAULT_TASK_NAME,
    model=None,
):
    """Transcribe audio file using faster-whisper"""
    # Allow caller to supply a pre-loaded model so we don't reload per file
    model = model or load_model(model_name, device="auto")

    print(f"Transcribing: {file_path}")
    transcribe_kwargs = dict(
        model_name=model_name,
        include_timestamps=include_timestamps,
        device="auto",
        model=model,
        task=task,
    )
    if language is not None:
        transcribe_kwargs["language"] = language

    result = transcribe_file(
        str(file_path),
        **transcribe_kwargs,
    )
    return result.text


def transcribe_audio_result(
    file_path,
    model_name=DEFAULT_MODEL_NAME,
    model=None,
    include_timestamps=True,
    language=None,
    task=DEFAULT_TASK_NAME,
):
    """Transcribe audio file using faster-whisper and return the full result object."""
    model = model or load_model(model_name, device="auto")
    transcribe_kwargs = dict(
        model_name=model_name,
        include_timestamps=include_timestamps,
        device="auto",
        model=model,
        task=task,
    )
    if language is not None:
        transcribe_kwargs["language"] = language

    result = transcribe_file(
        str(file_path),
        **transcribe_kwargs,
    )
    return result


def _run_postprocess_hook(output_file: Path, postprocess_command: str):
    command = shlex.split(postprocess_command)
    if not command:
        raise ValueError("--postprocess-cmd must include an executable command.")

    try:
        completed = subprocess.run(
            command + [str(output_file)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Postprocess hook command could not be executed: {command[0]}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        message = f"Postprocess hook failed for {output_file} with exit code {completed.returncode}."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message)


def _load_postprocess_plugin(plugin_spec: str):
    module_name, _, function_name = plugin_spec.partition(":")
    if not module_name or not function_name:
        raise ValueError("--postprocess-plugin must be in the format <module>:<callable>.")

    try:
        plugin_module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ValueError(f"Unable to import postprocess plugin module '{module_name}': {exc}") from exc
    try:
        plugin_handler = getattr(plugin_module, function_name)
    except AttributeError as exc:
        raise ValueError(f"Postprocess plugin not found: {plugin_spec}") from exc

    if not callable(plugin_handler):
        raise ValueError(f"Postprocess plugin target is not callable: {plugin_spec}")

    return plugin_handler


def _run_postprocess_plugin(output_file: Path, metadata: dict, plugin_handler):
    try:
        plugin_handler(str(output_file), dict(metadata))
    except Exception as exc:
        raise RuntimeError(f"Postprocess plugin failed for {output_file}: {exc}") from exc


def _record_postmortem_failure(output_dir: Path, file_path: Path, failure: dict):
    log_path = output_dir / POSTMORTEM_LOG_PATH
    payload = {
        "timestamp": time.time(),
        "source_path": str(file_path),
        "file": failure.get("file"),
        "error_type": failure.get("error_type"),
        "error": failure.get("error"),
        "attempts": failure.get("attempts"),
        "output_format": failure.get("output_format"),
    }
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"Warning: unable to write postmortem log {log_path}: {exc}")


def _collect_supported_file_tasks(directory: Path):
    raw_files = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]
    return build_stable_task_queue(raw_files)


def process_directory(
    directory_path,
    model_name=DEFAULT_MODEL_NAME,
    include_timestamps=True,
    resume=False,
    overwrite=False,
    retries=0,
    retry_delay=1.0,
    retry_backoff=2.0,
    max_workers=1,
    export_bundle=None,
    language=None,
    task=DEFAULT_TASK_NAME,
    postprocess_command=None,
    output_format=DEFAULT_OUTPUT_FORMAT,
    postprocess_plugin=None,
    annotation_export=None,
):
    """Process all supported audio/video files in the given directory"""
    _validate_cli_args(
        directory_path=directory_path,
        model_name=model_name,
        retries=retries,
        retry_delay=retry_delay,
        retry_backoff=retry_backoff,
        max_workers=max_workers,
        export_bundle=export_bundle,
        language=language,
        task=task,
        postprocess_command=postprocess_command,
        postprocess_plugin=postprocess_plugin,
        output_format=output_format,
        include_timestamps=include_timestamps,
        resume=resume,
        annotation_export=annotation_export,
    )
    start_time = time.perf_counter()
    directory = Path(directory_path)

    if not directory.exists():
        raise ValueError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")
    plugin_handler = None
    if postprocess_plugin is not None:
        plugin_handler = _load_postprocess_plugin(postprocess_plugin)

    file_tasks = _collect_supported_file_tasks(directory)
    supported_files = [task.source_path for task in file_tasks]
    stem_counts = Counter(path.stem for path in supported_files)
    stem_seen = Counter()

    summary = {
        "total": len(supported_files),
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "failures": [],
        "max_workers": max_workers,
        "annotation_export": None,
        "annotation_records": 0,
    }

    export_bundle_path = None
    if export_bundle is not None:
        export_bundle_path = _normalize_export_bundle_path(directory_path, export_bundle)
    annotation_export_path = None
    if annotation_export is not None:
        annotation_export_path = _normalize_annotation_export_path(directory_path, annotation_export)
    annotation_rows: list[dict] = []

    if not supported_files:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        print(
            f"No supported files found in: {directory}. "
            f"Supported extensions: {supported}"
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        summary.update({
            "elapsed_seconds": elapsed,
            "success": True,
            "throughput_files_per_second": 0.0,
        })
        if annotation_export_path is not None:
            try:
                _write_annotation_export(annotation_export_path, annotation_rows)
                summary["annotation_export"] = str(annotation_export_path)
                summary["annotation_records"] = len(annotation_rows)
            except Exception as exc:
                summary["annotation_export_error"] = str(exc)
                summary["success"] = False
        if export_bundle_path is not None:
            try:
                summary["export_bundle"] = str(export_bundle_path)
                _export_bundle(export_bundle_path, directory, summary)
            except Exception as exc:
                summary["bundle_error"] = str(exc)
                summary["success"] = False
        print("Done.")
        return summary

    async_policy = evaluate_async_execution_policy(
        requested_workers=max_workers,
        postprocess_command=postprocess_command,
        postprocess_plugin=postprocess_plugin,
    )
    if max_workers != 1:
        if async_policy.enabled:
            print(
                f"Info: --max-workers={max_workers} requested; async execution path will be used."
            )
        else:
            reason = async_policy.reason or "Async execution is not enabled for this run."
            print(
                f"Info: --max-workers={max_workers} requested; async execution disabled: {reason}"
            )

    # Load the model once for the entire run to avoid repeated downloads and RAM spikes
    model = _load_model_with_status(model_name)

    # Create output directory
    output_dir = directory / "transcriptions"
    output_dir.mkdir(exist_ok=True)

    # Process each audio file
    for file_task in file_tasks:
        file_path = file_task.source_path
        print(f"\nProcessing: {file_path.name}")

        stem_seen[file_path.stem] += 1
        occurrence = stem_seen[file_path.stem]
        if stem_counts[file_path.stem] <= 1:
            occurrence = 1

        output_file = _build_output_file_path(
            output_dir,
            source_path=file_path,
            output_format=output_format,
            occurrence=occurrence,
        )
        transcribe_file_include_timestamps = _effective_include_timestamps_for_output(
            output_format=output_format,
            include_timestamps=include_timestamps,
        )
        metadata_path = resolve_output_metadata_path(output_file)
        metadata_write_path = build_output_metadata_path(output_file)
        if output_file.exists():
            resume_skip = False
            if resume:
                resume_skip = should_skip_output_due_to_metadata(
                    source_path=file_path,
                    output_path=output_file,
                    metadata_path=metadata_path,
                    model_name=model_name,
                    include_timestamps=transcribe_file_include_timestamps,
                    output_format=output_format,
                    task=task,
                    language=language,
                )

            if overwrite is False and resume_skip:
                summary["skipped"] += 1
                print(f"Resuming: skipping already completed output: {output_file}")
                continue
            if not overwrite and not resume:
                summary["skipped"] += 1
                print(f"Skipping existing output file: {output_file}")
                continue

        attempts = 0
        while True:
            attempts += 1
            try:
                result = transcribe_audio_result(
                    file_path,
                    model_name=model_name,
                    include_timestamps=transcribe_file_include_timestamps,
                    language=language,
                    task=task,
                    model=model,
                )
                transcription = _render_output_text(result, output_format)

                # Save transcription to file
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(transcription)
                print(f"Transcription saved to: {output_file}")
                metadata = {
                    "source_path": str(file_path),
                    "output_path": str(output_file),
                    "model": model_name,
                    "include_timestamps": transcribe_file_include_timestamps,
                    "language": language,
                    "task": task,
                    "overwrite": overwrite,
                    "retries": retries,
                    "retry_delay": retry_delay,
                    "retry_backoff": retry_backoff,
                    "output_format": output_format,
                    "processed_at": time.time(),
                }
                if postprocess_command:
                    _run_postprocess_hook(output_file, postprocess_command)
                if postprocess_plugin:
                    _run_postprocess_plugin(output_file, metadata, plugin_handler)
                if annotation_export_path is not None:
                    annotation_rows.extend(
                        _annotation_export_rows(file_path, output_file, result, metadata)
                    )
                try:
                    _write_output_metadata(
                        metadata_write_path,
                        file_path,
                        output_file,
                        metadata["model"],
                        metadata["include_timestamps"],
                        metadata["language"],
                        metadata["task"],
                        metadata["overwrite"],
                        metadata["retries"],
                        metadata["retry_delay"],
                        metadata["retry_backoff"],
                        metadata["output_format"],
                    )
                except Exception as exc:
                    print(f"Warning: metadata write failed for {output_file}: {exc}")
                summary["processed"] += 1
                break
            except Exception as exc:
                if attempts <= retries:
                    if retry_delay > 0:
                        delay = retry_delay * (retry_backoff ** (attempts - 1))
                        time.sleep(delay)
                    print(
                        f"Retrying {file_path.name} (attempt {attempts}/{retries}) after failure: {str(exc)}"
                    )
                    continue
                failure = {
                    "file": str(file_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "attempts": attempts,
                    "output_format": output_format,
                }
                summary["failed"] += 1
                summary["failures"].append(failure)
                _record_postmortem_failure(output_dir, file_path, failure)
                print(f"Error processing {file_path.name}: {str(exc)}")
                break

    elapsed = round(time.perf_counter() - start_time, 3)
    throughput = round(summary["processed"] / elapsed, 3) if elapsed > 0 else 0.0
    summary.update({
        "elapsed_seconds": elapsed,
        "success": summary["failed"] == 0,
        "throughput_files_per_second": throughput,
    })
    if annotation_export_path is not None:
        try:
            _write_annotation_export(annotation_export_path, annotation_rows)
            summary["annotation_export"] = str(annotation_export_path)
            summary["annotation_records"] = len(annotation_rows)
        except Exception as exc:
            summary["annotation_export_error"] = str(exc)
            summary["success"] = False
    if export_bundle_path is not None:
        try:
            summary["export_bundle"] = str(export_bundle_path)
            _export_bundle(export_bundle_path, directory, summary)
        except Exception as exc:
            summary["bundle_error"] = str(exc)
            summary["success"] = False

    print(
        "Done. "
        f"Processed {summary['processed']}/{summary['total']} files "
        f"({summary['failed']} failed, {summary['skipped']} skipped)."
    )
    print(
        f"Success: {summary['success']} | Elapsed: {summary['elapsed_seconds']}s | "
        f"Throughput: {summary['throughput_files_per_second']} files/sec"
    )
    return summary

def main():
    try:
        _validate_runtime_python_version()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Transcribe audio files using faster-whisper")
    parser.add_argument("directory", help="Directory containing audio files to transcribe")
    parser.add_argument(
        "--model",
        default=None,
        choices=sorted(SUPPORTED_MODELS),
        help=f"faster-whisper model to use (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to .whisperbatch JSON config file (defaults to ./directory/.whisperbatch if present)"
    )
    timestamp_group = parser.add_mutually_exclusive_group()
    timestamp_group.add_argument(
        "--timestamps",
        dest="include_timestamps",
        action="store_true",
        help="Enable timestamps in output"
    )
    timestamp_group.add_argument(
        "--no-timestamps",
        dest="include_timestamps",
        action="store_false",
        help="Disable timestamps in output"
    )
    parser.set_defaults(include_timestamps=None)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        dest="overwrite",
        default=None,
        help="Overwrite existing output files when set"
    )
    parser.set_defaults(overwrite=None)
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Number of retry attempts after failed transcription"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=None,
        help="Delay in seconds between retries"
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=None,
        help="Retry backoff multiplier per attempt (e.g., 2.0 for exponential backoff)"
    )
    parser.add_argument(
        "--output-format",
        choices=sorted(SUPPORTED_OUTPUT_FORMATS),
        default=None,
        help=f"Output format: {', '.join(sorted(SUPPORTED_OUTPUT_FORMATS))}."
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Emit final summary as JSON"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=None,
        help="Skip files that have valid metadata from a prior run",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Number of worker threads to use in future parallel mode (currently single-threaded)."
    )
    parser.add_argument(
        "--postprocess-cmd",
        dest="postprocess_command",
        default=None,
        help="Run this command after each output file is written, with output path passed as final arg.",
    )
    parser.add_argument(
        "--postprocess-plugin",
        dest="postprocess_plugin",
        default=None,
        help=(
            "Run this Python callable after each output file is written using "
            "<module>:<callable> (module is imported when the hook runs)."
        ),
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Whisper language hint (e.g., en, de, fr).",
    )
    parser.add_argument(
        "--language-profile",
        dest="language_profile",
        default=None,
        help="Apply a named language profile from .whisperbatch language_profiles.",
    )
    parser.add_argument(
        "--export-bundle",
        dest="export_bundle",
        default=None,
        help="Create a zip export at this path with transcription outputs and run_summary.json."
    )
    parser.add_argument(
        "--task",
        choices=sorted(SUPPORTED_TASKS),
        default=None,
        help=(
            f"Whisper task to run. Supported values: {', '.join(sorted(SUPPORTED_TASKS))}. "
            f"(default: {DEFAULT_TASK_NAME})"
        )
    )
    parser.add_argument(
        "--annotation-export",
        dest="annotation_export",
        default=None,
        help="Write per-segment annotations to CSV (default) or JSONL for downstream indexing."
    )
    parser.add_argument(
        "--speaker-profile",
        dest="speaker_profile",
        default=None,
        help="Apply a named speaker profile from .whisperbatch speaker_profiles.",
    )

    args = parser.parse_args()

    options = _resolve_options(args.directory, args)

    try:
        summary = process_directory(
            args.directory,
            options["model_name"],
            options["include_timestamps"],
            overwrite=options["overwrite"],
            resume=options["resume"],
            retries=options["retries"],
            retry_delay=options["retry_delay"],
            retry_backoff=options["retry_backoff"],
            max_workers=options["max_workers"],
            export_bundle=options["export_bundle"],
            language=options["language"],
            task=options["task"],
            postprocess_command=options["postprocess_command"],
            postprocess_plugin=options["postprocess_plugin"],
            output_format=options["output_format"],
            annotation_export=options["annotation_export"],
        )
        if args.summary_json:
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

    return 0


def cli():
    """Console-script-compatible entrypoint."""
    raise SystemExit(main())


if __name__ == "__main__":
    exit(main())
