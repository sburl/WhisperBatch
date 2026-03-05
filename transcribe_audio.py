#!/usr/bin/env python3

import argparse
import time
from collections import Counter
from pathlib import Path

from whisper_batch_core import (
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_FORMAT,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MODELS,
    SUPPORTED_OUTPUT_FORMATS,
    load_model,
    render_output_text,
    transcribe_file,
)


def _build_output_file_path(output_dir, stem, output_format, occurrence=1):
    """Build an output path, adding a collision-safe suffix when needed."""
    base = f"{stem}_transcription"
    if occurrence > 1:
        base = f"{base}_{occurrence}"
    return output_dir / f"{base}.{output_format}"


def transcribe_audio(file_path, model_name=DEFAULT_MODEL_NAME, include_timestamps=True,
                     output_format=DEFAULT_OUTPUT_FORMAT, model=None):
    """Transcribe audio file using faster-whisper"""
    model = model or load_model(model_name, device="auto")

    print(f"Transcribing: {file_path}")
    result = transcribe_file(
        str(file_path),
        model_name=model_name,
        include_timestamps=include_timestamps,
        device="auto",
        model=model,
        task="transcribe"
    )
    return render_output_text(result.segments, output_format=output_format,
                              include_timestamps=include_timestamps)


def process_directory(directory_path, model_name=DEFAULT_MODEL_NAME,
                      include_timestamps=True, output_format=DEFAULT_OUTPUT_FORMAT):
    """Process all supported audio/video files in the given directory."""
    directory = Path(directory_path).expanduser()

    if not directory.exists():
        raise ValueError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    if model_name not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model '{model_name}'. "
            f"Supported: {', '.join(SUPPORTED_MODELS)}"
        )

    # Collect and sort matching files before loading the model
    media_files = sorted(
        (entry for entry in directory.iterdir()
         if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: (p.name.lower(), p.name),
    )

    if not media_files:
        print("No supported media files found in the directory.")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    # Track stem occurrences so same-stem files don't overwrite each other
    stem_counter = Counter()

    # Load the model once for the entire run
    print(f"Loading faster-whisper model: {model_name}")
    model = load_model(model_name, device="auto")

    # Create output directory
    output_dir = directory / "transcriptions"
    output_dir.mkdir(exist_ok=True)

    start_time = time.time()
    success = 0
    failed = 0

    for file_path in media_files:
        stem = file_path.stem
        stem_counter[stem] += 1
        occurrence = stem_counter[stem]

        print(f"\nProcessing: {file_path.name}")
        try:
            transcription = transcribe_audio(
                file_path, model_name, include_timestamps,
                output_format=output_format, model=model,
            )

            output_file = _build_output_file_path(
                output_dir, stem, output_format, occurrence,
            )
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcription)
            print(f"Transcription saved to: {output_file}")
            success += 1

        except Exception as e:
            print(f"Error processing {file_path.name}: {str(e)}")
            failed += 1

    elapsed = time.time() - start_time
    total = success + failed
    print(f"\nDone. {success} succeeded, {failed} failed out of {total} files ({elapsed:.1f}s)")

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": 0,
        "elapsed_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files using faster-whisper")
    parser.add_argument("directory", help="Directory containing audio files to transcribe")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME,
                      choices=list(SUPPORTED_MODELS),
                      help=f"faster-whisper model to use (default: {DEFAULT_MODEL_NAME})")
    parser.add_argument("--no-timestamps", action="store_true",
                      help="Disable timestamps in output")
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT,
                      choices=sorted(SUPPORTED_OUTPUT_FORMATS),
                      help=f"Output format (default: {DEFAULT_OUTPUT_FORMAT})")

    args = parser.parse_args()

    try:
        process_directory(
            args.directory, args.model,
            not args.no_timestamps, args.output_format,
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

    return 0


def cli():
    """Console-script-compatible entrypoint."""
    raise SystemExit(main())

if __name__ == "__main__":
    cli()
