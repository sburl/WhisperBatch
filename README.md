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
```

The CLI writes one transcript per media file into `transcriptions/` and prints a run summary:
`success`, `failed`, `skipped`, and `total`.

> Note: advanced workflow flags such as `--resume`, retries, worker controls, and
> post-process hooks are not part of this CLI branch.

GUI metadata and resume:
- GUI writes a metadata sidecar for each output file: `<output> .metadata.json`
- GUI **Resume completed files** checks metadata to skip files already completed
  with matching model/output settings


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
   python transcribe_audio.py /path/to/folder --model base
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
