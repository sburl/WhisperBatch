# WhisperBatch

**Created:** 2025-05-09-01-32
**Last Updated:** 2026-01-09-17-49

A Python package and GUI application for transcribing audio files using [faster-whisper](https://github.com/Systran/faster-whisper). Use the GUI for batch processing with a user-friendly interface, or install the package to use the transcription API in your own Python projects.

---

## Highlights
- **Multiple Model Support** – tiny, base, small, medium, large-v3
- **Batch Queue** – add/reorder/remove files while paused
- **Progress & status** – per-file status plus batch summary
- **Timestamps** – optional per-segment timecodes
- **Cross-platform** – macOS, Linux, Windows (Python ≥ 3.9)

---

## Quick-start (all platforms)
```bash
# clone project
cd AudioTranscribe

# one-step setup (creates .venv, installs deps, handles Apple-silicon quirks)
chmod +x setup.sh
./setup.sh

# activate env & run GUI
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python transcribe_gui.py

# run CLI directly after install (if not already installed by setup.sh)
pip install -e .
whisper-batch /path/to/folder --model base
```

GUI resume support:
Use the **Resume completed files** checkbox in the GUI to skip files that already have a valid metadata sidecar from a previous run using the same model and timestamp settings.
If metadata is missing or stale, the file is reprocessed (unless `Overwrite outputs` is disabled and a transcription already exists).

---

## Apple-Silicon notes (M-series Macs)
1. The setup script auto-detects arm64 and ensures the **native** PyTorch CPU wheel is installed (`torch==2.4.1`).
2. When you choose **Device = Auto** (default) the program now *automatically falls back* to **CPU + int8** compute-type. This avoids current CTranslate2/Metal seg-faults while still running ~2× real-time on an M1/M2/M3.
3. Once a stable CTranslate2 Metal backend is released the GUI will switch back to GPU automatically.

If you ever see the linker error below you are running an x86-64 wheel under Rosetta:
```
macOS 26 (2601) or later required, have instead 16 (1601) !
```
Fix with:
```bash
pip uninstall -y torch
pip install --no-cache-dir --force-reinstall torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
```

---

## Requirements
- Python 3.9 – 3.13 (3.14 wheels are typically unavailable for some dependencies at publication time)

### Python policy

WhisperBatch is validated on Python 3.9 through 3.13 in CI and in-repo tooling.
Runs on older Python versions are blocked by design, and newer versions may fail if required
runtime dependencies have not added compatible wheels yet.

If you install on a Python version outside this range, run `setup.sh` may still succeed,
but CLI/GUI startup should be considered unsupported until dependency support and
runtime validation are explicitly expanded.

- FFmpeg in PATH
- Required pip packages (installed by `setup.sh`):
  - faster-whisper
  - torch (CPU wheel by default)
  - numpy, ctranslate2, tqdm, requests

For local development and CI checks, install both runtime and tooling dependencies:

```bash
pip install -r requirements-dev.txt
```

If you want to keep dependency resolution reproducible for local tooling workflows, install `pip-tools` (included in `requirements-dev.txt`) and generate a pinned lockfile with:

```bash
pip-compile --generate-hashes requirements-dev.txt --output-file requirements-dev.lock
```

---

## Running headless CLI
Batch-transcribe an entire directory without the GUI:
```bash
python transcribe_audio.py /path/to/folder --model base
# or, after install:
whisper-batch /path/to/folder --model base
```

The first time a model is used, the CLI prints whether it is cached locally and where it will be downloaded. Re-running with the same model avoids download when possible and prints fast cache load timing.

GUI usage tip: the **Add Folder** button imports supported media files recursively from nested directories.

Useful CLI options:

```bash
# Disable timestamps
python transcribe_audio.py /path/to/folder --no-timestamps

# Save JSON / SRT / VTT output formats
python transcribe_audio.py /path/to/folder --output-format json
python transcribe_audio.py /path/to/folder --output-format srt
python transcribe_audio.py /path/to/folder --output-format vtt

# Get machine-readable JSON summary and robust retry behavior
python transcribe_audio.py /path/to/folder --summary-json --retries 2 --retry-delay 0.5
# Use exponential backoff multiplier for retries
python transcribe_audio.py /path/to/folder --retries 3 --retry-delay 1 --retry-backoff 2.0

# Force overwrite for existing outputs
python transcribe_audio.py /path/to/folder --overwrite

# Set worker intent (single-worker in current release)
python transcribe_audio.py /path/to/folder --max-workers 4

# Run a postprocessing command per output
python transcribe_audio.py /path/to/folder --postprocess-cmd "python scripts/postprocess.py --format txt"

`--postprocess-cmd` appends the generated output path as the final positional argument.

# Build a zip bundle of outputs after the run
python transcribe_audio.py /path/to/folder --export-bundle run_bundle.zip

`--export-bundle` creates a zip at the provided path (default relative to the target directory) containing the `transcriptions/` tree and `run_summary.json`.

# Export per-segment annotations for search/indexing
python transcribe_audio.py /path/to/folder --annotation-export annotations.jsonl

`--annotation-export` writes one row per segment in either CSV (default `*.csv`) or JSONL (`*.jsonl`) format.

# Run a post-process plugin on each output
python transcribe_audio.py /path/to/folder --postprocess-plugin "sample_postprocess_plugins:redact_email_addresses"

See [Post-process plugin contract](docs/postprocess-plugin-contract.md) for the
interface details, metadata payload, and extension notes.

`--postprocess-plugin` accepts `<module>:<callable>` and calls it with `(output_path, metadata)` where metadata
is the runtime metadata object written to `*_transcription.txt.metadata.json`.

# Force a Whisper language hint
python transcribe_audio.py /path/to/folder --language en

`--language` passes a language hint (`en`, `de`, `fr`, etc.) to whisper for all inputs in the run.

# Use profile presets for reusable language/task combinations
python transcribe_audio.py /path/to/folder --language-profile interview-es
python transcribe_audio.py /path/to/folder --speaker-profile guest_translate

`--language-profile` and `--speaker-profile` load presets from `.whisperbatch` and apply the profile options to the run.

# Run translation mode
python transcribe_audio.py /path/to/folder --task translate

`--task` accepts `transcribe` (default) or `translate`.

# Continue an interrupted run and skip files completed in same metadata
python transcribe_audio.py /path/to/folder --resume

# Use a project config file for defaults
Create `/path/to/folder/.whisperbatch`:
```json
{
  "model": "base",
  "timestamps": false,
  "overwrite": true,
  "retries": 2,
  "retry_delay": 0.5,
  "retry_backoff": 2.0,
  "output_format": "json",
  "max_workers": 2,
  "postprocess_command": "python scripts/postprocess.py --format txt",
  "postprocess_plugin": "sample_postprocess_plugins:redact_email_addresses",
  "export_bundle": "run_bundle.zip",
  "annotation_export": "annotations.csv",
  "language_profiles": {
    "interview-es": {
      "language": "es",
      "task": "transcribe",
      "model": "base"
    },
    "interview-fr-translate": {
      "language": "fr",
      "task": "translate"
    }
  },
  "speaker_profiles": {
    "guest-translate": {
      "language": "en",
      "task": "translate"
    },
    "host-default": {
      "language": "en",
      "task": "transcribe"
    }
  },
  "language_profile": "interview-fr-translate",
  "speaker_profile": "guest-translate",
  "language": "en",
  "task": "translate",
  "resume": true
}
```
Profile objects support the same option keys as CLI flags (including `model`), so a profile can switch model/task/language together for a run. CLI `--model` remains the highest-priority override.

Then run:
```bash
python transcribe_audio.py /path/to/folder
```
CLI flags always override config values:
```bash
python transcribe_audio.py /path/to/folder --model large-v3 --no-timestamps --retries 0
```

# Provenance metadata
When a run succeeds, each output file gets a metadata sidecar:
`*_transcription.txt.metadata.json` (or the matching format-specific suffix).

Metadata includes source file, output path, runtime options, and processing timestamp.

When a file fails, the run summary includes a `failures` array with the file path,
error type, and retry count. The same failure information is also written to
`transcriptions/postmortem.jsonl` for quick CLI-side triage.

### Resume a previously interrupted run

You can resume where a run left off with:

```bash
python transcribe_audio.py /path/to/folder --resume
```

Resume uses the metadata sidecar and skips files that were already completed with the same
options used for the current run.

If options changed or metadata is missing, that file is reprocessed.

---

## Core Package

The non-GUI transcription utilities live in `whisper_batch_core/`. Install locally:

```bash
pip install -e .
```

Example usage:

```python
from whisper_batch_core import transcribe_file

result = transcribe_file("path/to/audio.wav", model_name="base")
text = result.text
```

API options:
- `model_name`: model size such as `tiny`, `base`, `small`, `medium`, `large-v3`
- `device`: `auto`, `cpu`, or `cuda`
- `compute_type`: `float16`, `int8_float16`, `int8`, or `float32`
- `include_timestamps`: include segment timestamps in the output text
- `task`: `transcribe` or `translate`

### Model-load failure playbook (cache/download incidents)

If the CLI/GUI reports model-load failures:

1. Confirm the error is not a temporary network event and retry once.
2. Clear local model cache artifacts and retry:
   ```bash
   # Default cache location
   rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-*

   # Or use your configured Hugging Face cache overrides
   if [ -n "${HF_HOME:-}" ]; then
     rm -rf "$HF_HOME/hub/models--Systran--faster-whisper-*"
   fi
   if [ -n "${HUGGINGFACE_HUB_CACHE:-}" ]; then
     rm -rf "$HUGGINGFACE_HUB_CACHE/models--Systran--faster-whisper-*"
   fi
   if [ -n "${XDG_CACHE_HOME:-}" ] && [ -z "${HUGGINGFACE_HUB_CACHE:-}" ] && [ -z "${HF_HOME:-}" ]; then
     rm -rf "$XDG_CACHE_HOME/huggingface/hub/models--Systran--faster-whisper-*"
   fi
   rm -rf ~/.cache/torch/
   ```
3. Re-run with a smaller model first to verify runtime health:
   ```bash
   python transcribe_audio.py /path/to/folder --model base --resume
   ```
4. If it still fails, capture and include:
   - Python version
   - CLI command
   - last 40 lines of the traceback

---

## Troubleshooting
| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: _tkinter` | Reinstall Homebrew `python@3.x` **after** `brew install tcl-tk`, or use `/usr/bin/python3`. |
| `macOS 26 / 16` loader abort | You installed an x86-64 PyTorch wheel – reinstall arm64 CPU wheel (see above). |
| Segmentation fault on model load | Automatically mitigated by CPU fallback; update faster-whisper & CTranslate2 when new GPU wheels land. |

---

MIT License © 2026
