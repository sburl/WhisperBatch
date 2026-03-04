#!/usr/bin/env python3

import argparse
from pathlib import Path

from whisper_batch_core import (
    SUPPORTED_EXTENSIONS,
    load_model,
    transcribe_file,
)

def _collect_supported_files(directory: Path):
    entries = [path for path in directory.iterdir() if path.is_file()]
    supported_files = [path for path in entries if path.suffix.lower() in SUPPORTED_EXTENSIONS]
    skipped_files = len(entries) - len(supported_files)
    supported_files.sort(key=lambda path: (path.name.lower(), path.name))
    return supported_files, skipped_files


def transcribe_audio(file_path, model_name="large-v3", include_timestamps=True, model=None):
    """Transcribe audio file using faster-whisper"""
    # Allow caller to supply a pre-loaded model so we don't reload per file
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
    return result.text

def process_directory(directory_path, model_name="large-v3", include_timestamps=True):
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

    audio_files, skipped_files = _collect_supported_files(directory)
    summary = {
        "total": len(audio_files),
        "success": 0,
        "failed": 0,
        "skipped": skipped_files,
    }

    if not audio_files:
        print("No supported audio files found in directory.")
        print(
            "Summary: "
            f"success={summary['success']}, failed={summary['failed']}, "
            f"skipped={summary['skipped']}, total={summary['total']}"
        )
        return summary
    
    # Process each audio file
    for file_path in audio_files:
        print(f"\nProcessing: {file_path.name}")
        try:
            transcription = transcribe_audio(file_path, model_name, include_timestamps, model=model)

            # Save transcription to file
            output_file = output_dir / f"{file_path.stem}_transcription.txt"
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
    
    args = parser.parse_args()
    
    try:
        process_directory(args.directory, args.model, not args.no_timestamps)
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 
