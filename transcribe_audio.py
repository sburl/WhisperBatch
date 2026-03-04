#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import time

from whisper_batch_core import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MODELS,
    SUPPORTED_OUTPUT_FORMATS,
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_FORMAT,
    effective_include_timestamps as _core_effective_include_timestamps,
    format_timestamp_with_millis as _core_format_timestamp_with_millis,
    load_model,
    render_output_text as _core_render_output_text,
    render_srt as _core_render_srt,
    render_vtt as _core_render_vtt,
    result_to_json_payload as _core_result_to_json_payload,
    transcribe_file,
)


def _group_files_by_stem(paths):
    grouped = {}
    for path in paths:
        grouped.setdefault(path.stem, []).append(path)
    return grouped

def _build_output_file_path(
    output_dir: Path,
    input_path: Path,
    output_format: str,
    stem_groups,
    reserved_output_paths,
) -> Path:
    output_extension = _output_extension(output_format)
    stem_candidates = stem_groups.get(input_path.stem, [input_path])
    is_primary_stem_path = stem_candidates[0] == input_path

    if len(stem_candidates) == 1 or is_primary_stem_path:
        candidate = output_dir / f"{input_path.stem}_transcription.{output_extension}"
    else:
        suffix = input_path.suffix.lstrip(".") or "unknown"
        candidate = output_dir / f"{input_path.stem}_{suffix}_transcription.{output_extension}"

    if candidate in reserved_output_paths:
        index = 1
        while True:
            indexed_candidate = output_dir / f"{candidate.stem}_{index}{candidate.suffix}"
            if indexed_candidate not in reserved_output_paths:
                candidate = indexed_candidate
                break
            index += 1

    reserved_output_paths.add(candidate)
    return candidate


def _collect_supported_files(directory: Path):
    files = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]
    files.sort(key=lambda path: (path.name.lower(), path.name))
    return files


def _format_timestamp_with_millis(seconds, separator="."):
    return _core_format_timestamp_with_millis(seconds, separator=separator)


def _render_srt(segments):
    return _core_render_srt(segments)


def _render_vtt(segments):
    return _core_render_vtt(segments)


def _result_to_json_payload(segments, include_timestamps):
    return _core_result_to_json_payload(segments, include_timestamps=include_timestamps)


def _effective_include_timestamps(output_format: str, include_timestamps: bool):
    return _core_effective_include_timestamps(output_format, include_timestamps)


def _render_output_text(segments, output_format: str, include_timestamps: bool):
    return _core_render_output_text(
        segments,
        output_format=output_format,
        include_timestamps=include_timestamps,
    )


def _output_extension(output_format: str):
    return output_format


def transcribe_audio(
    file_path,
    model_name=DEFAULT_MODEL_NAME,
    include_timestamps=True,
    model=None,
    output_format=DEFAULT_OUTPUT_FORMAT,
    verbose=True,
):
    """Transcribe audio file using faster-whisper"""
    # Allow caller to supply a pre-loaded model so we don't reload per file
    model = model or load_model(model_name, device="auto")
    
    if verbose:
        print(f"Transcribing: {file_path}")
    result = transcribe_file(
        str(file_path),
        model_name=model_name,
        include_timestamps=_effective_include_timestamps(output_format, include_timestamps),
        device="auto",
        model=model,
        task="transcribe"
    )
    return _render_output_text(result.segments, output_format, include_timestamps)


def _transcribe_with_retries(
    file_path,
    model_name,
    include_timestamps,
    model,
    output_format,
    max_retries,
    verbose,
):
    attempts = 0
    while True:
        try:
            return transcribe_audio(
                file_path,
                model_name,
                include_timestamps,
                model=model,
                output_format=output_format,
                verbose=verbose,
            )
        except Exception as exc:
            attempts += 1
            if attempts > max_retries:
                raise
            if verbose:
                print(
                    f"Retrying {file_path.name}: attempt {attempts}/{max_retries} after error: {exc}"
                )

def process_directory(
    directory_path,
    model_name=DEFAULT_MODEL_NAME,
    include_timestamps=True,
    output_format=DEFAULT_OUTPUT_FORMAT,
    overwrite=False,
    summary_json=False,
    max_retries=0,
):
    """Process all supported audio/video files in the given directory"""
    directory = Path(directory_path)
    
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")
    if max_retries < 0:
        raise ValueError(f"max_retries must be >= 0: {max_retries}")
    if model_name not in SUPPORTED_MODELS:
        supported = ", ".join(SUPPORTED_MODELS)
        raise ValueError(f"Unsupported model: {model_name}. Supported models: {supported}")
    verbose = not summary_json
    
    # Load the model once for the entire run to avoid repeated downloads and RAM spikes
    if verbose:
        print(f"Loading faster-whisper model: {model_name}")
    model = load_model(model_name, device="auto")
    
    # Create output directory
    output_dir = directory / "transcriptions"
    output_dir.mkdir(exist_ok=True)
    
    supported_files = _collect_supported_files(directory)
    stem_groups = _group_files_by_stem(supported_files)
    reserved_output_paths = set()
    total_candidates = len(supported_files)
    total_entries = len([path for path in directory.iterdir() if path.is_file()])
    summary = {
        "total": total_candidates,
        "success": 0,
        "failed": 0,
        "skipped": total_entries - total_candidates,
    }

    start_time = time.perf_counter()

    # Process each audio file
    for file_path in supported_files:
        if verbose:
            print(f"\nProcessing: {file_path.name}")
        try:
            output_file = _build_output_file_path(
                output_dir,
                file_path,
                output_format,
                stem_groups,
                reserved_output_paths,
            )
            if output_file.exists() and not overwrite:
                if verbose:
                    print(f"Skipping existing output: {output_file}")
                summary["skipped"] += 1
                continue

            transcription = _transcribe_with_retries(
                file_path,
                model_name,
                include_timestamps,
                output_format=output_format,
                model=model,
                max_retries=max_retries,
                verbose=verbose,
            )
            
            # Save transcription to file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcription)
            if verbose:
                print(f"Transcription saved to: {output_file}")
            summary["success"] += 1
                
        except Exception as e:
            if verbose:
                print(f"Error processing {file_path.name}: {str(e)}")
            summary["failed"] += 1

    elapsed_seconds = round(time.perf_counter() - start_time, 3)
    summary["elapsed_seconds"] = elapsed_seconds
    throughput = summary["success"] / elapsed_seconds if elapsed_seconds > 0 else 0.0
    summary["throughput_files_per_second"] = throughput

    if summary_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            "Summary: "
            f"success={summary['success']}, failed={summary['failed']}, "
            f"skipped={summary['skipped']}, total={summary['total']}"
        )
    return summary

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files using faster-whisper")
    parser.add_argument("directory", help="Directory containing audio files to transcribe")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        choices=sorted(SUPPORTED_MODELS),
        help=f"faster-whisper model to use (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument("--no-timestamps", action="store_true",
                      help="Disable timestamps in output")
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=sorted(SUPPORTED_OUTPUT_FORMATS),
        help=f"Output format to write for each transcription (default: {DEFAULT_OUTPUT_FORMAT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript files (default: skip)",
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Emit summary as a single JSON object",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum retries for transient transcription failures (default: 0)",
    )
    
    args = parser.parse_args()
    
    try:
        process_directory(
            args.directory,
            args.model,
            not args.no_timestamps,
            args.output_format,
            overwrite=args.overwrite,
            summary_json=args.summary_json,
            max_retries=args.max_retries,
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 
