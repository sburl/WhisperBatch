#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from whisper_batch_core import (
    SUPPORTED_EXTENSIONS,
    render_plain_text,
    render_timestamped_text,
    load_model,
    transcribe_file,
)

SUPPORTED_OUTPUT_FORMATS = {"txt", "json", "srt", "vtt"}
TIMESTAMP_ONLY_OUTPUT_FORMATS = {"srt", "vtt"}


def _build_output_file_path(output_dir: Path, input_path: Path, output_format: str) -> Path:
    return output_dir / f"{input_path.stem}_transcription.{_output_extension(output_format)}"


def _collect_supported_files(directory: Path):
    files = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]
    files.sort(key=lambda path: (path.name.lower(), path.name))
    return files


def _format_timestamp_with_millis(seconds, separator="."):
    total_ms = int(round(float(seconds) * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def _render_srt(segments):
    lines = []
    for index, segment in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(
            f"{_format_timestamp_with_millis(segment.start, ',')} --> {_format_timestamp_with_millis(segment.end, ',')}"
        )
        lines.append((segment.text or "").strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_vtt(segments):
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(
            f"{_format_timestamp_with_millis(segment.start, '.')} --> {_format_timestamp_with_millis(segment.end, '.')}"
        )
        lines.append((segment.text or "").strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _result_to_json_payload(segments, include_timestamps):
    return {
        "text": " ".join((segment.text or "").strip() for segment in segments).strip(),
        "segments": [
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": (segment.text or "").strip(),
                "include_timestamps": bool(include_timestamps),
            }
            for segment in segments
        ],
    }


def _effective_include_timestamps(output_format: str, include_timestamps: bool):
    if output_format in TIMESTAMP_ONLY_OUTPUT_FORMATS:
        return True
    return bool(include_timestamps)


def _render_output_text(segments, output_format: str, include_timestamps: bool):
    if output_format == "txt":
        if _effective_include_timestamps(output_format, include_timestamps):
            return render_timestamped_text(segments)
        return render_plain_text(segments)
    if output_format == "json":
        return json.dumps(_result_to_json_payload(segments, include_timestamps), ensure_ascii=False, indent=2)
    if output_format == "srt":
        return _render_srt(segments)
    if output_format == "vtt":
        return _render_vtt(segments)
    raise ValueError(f"Unsupported output format: {output_format}")


def _output_extension(output_format: str):
    return output_format


def transcribe_audio(file_path, model_name="large-v3", include_timestamps=True, model=None, output_format="txt"):
    """Transcribe audio file using faster-whisper"""
    # Allow caller to supply a pre-loaded model so we don't reload per file
    model = model or load_model(model_name, device="auto")
    
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

def process_directory(
    directory_path,
    model_name="large-v3",
    include_timestamps=True,
    output_format="txt",
    overwrite=False,
):
    """Process all supported audio/video files in the given directory"""
    directory = Path(directory_path)
    
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")
    
    # Load the model once for the entire run to avoid repeated downloads and RAM spikes
    print(f"Loading faster-whisper model: {model_name}")
    model = load_model(model_name, device="auto")
    
    # Create output directory
    output_dir = directory / "transcriptions"
    output_dir.mkdir(exist_ok=True)
    
    supported_files = _collect_supported_files(directory)
    total_candidates = len(supported_files)
    total_entries = len([path for path in directory.iterdir() if path.is_file()])
    summary = {
        "total": total_candidates,
        "success": 0,
        "failed": 0,
        "skipped": total_entries - total_candidates,
    }

    # Process each audio file
    for file_path in supported_files:
        print(f"\nProcessing: {file_path.name}")
        try:
            output_file = _build_output_file_path(output_dir, file_path, output_format)
            if output_file.exists() and not overwrite:
                print(f"Skipping existing output: {output_file}")
                summary["skipped"] += 1
                continue

            transcription = transcribe_audio(
                file_path,
                model_name,
                include_timestamps,
                model=model,
                output_format=output_format,
            )
            
            # Save transcription to file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcription)
            print(f"Transcription saved to: {output_file}")
            summary["success"] += 1
                
        except Exception as e:
            print(f"Error processing {file_path.name}: {str(e)}")
            summary["failed"] += 1

    print(
        "Summary: "
        f"success={summary['success']}, failed={summary['failed']}, "
        f"skipped={summary['skipped']}, total={summary['total']}"
    )
    return summary

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files using faster-whisper")
    parser.add_argument("directory", help="Directory containing audio files to transcribe")
    parser.add_argument("--model", default="large-v3", 
                      choices=["tiny", "base", "small", "medium", "large-v3"],
                      help="faster-whisper model to use (default: large-v3)")
    parser.add_argument("--no-timestamps", action="store_true",
                      help="Disable timestamps in output")
    parser.add_argument(
        "--output-format",
        default="txt",
        choices=sorted(SUPPORTED_OUTPUT_FORMATS),
        help="Output format to write for each transcription (default: txt)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript files (default: skip)",
    )
    
    args = parser.parse_args()
    
    try:
        process_directory(
            args.directory,
            args.model,
            not args.no_timestamps,
            args.output_format,
            overwrite=args.overwrite,
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 
