# WhisperBatch post-process plugin contract

**Created:** 2026-03-03-17-23
**Last Updated:** 2026-03-03-17-23

This document describes the Python post-processing plugin interface introduced by
`--postprocess-plugin`.

## Contract

The `--postprocess-plugin` flag expects a Python callable reference in the form:

```bash
--postprocess-plugin "module_name:function_name"
```

At runtime, WhisperBatch:

1. Imports the target module.
2. Loads the target attribute.
3. Verifies it is callable.
4. Calls it for every successfully generated output file.
5. Loads the callable once per run and reuses it for each file.

The callable receives two positional arguments:

- `output_path` (`str`): path to the generated output file.
- `metadata` (`dict`): runtime metadata for the completed file, including:
  - `source_path`
  - `output_path`
  - `model`
  - `language`
  - `task`
  - `output_format`
  - `include_timestamps`
  - `overwrite`
  - `retries`
  - `retry_delay`
  - `retry_backoff`
  - `processed_at`

Return value is ignored.

If the callable raises any exception, WhisperBatch treats it as a failed file and
adds a failure to the run summary.

## Runtime expectations

- Keep plugins deterministic when possible, especially if you combine `--resume`.
- Keep operations local to the output file path and metadata.
- Avoid heavy side effects in the hot path (this hook runs per file).
- Use plain UTF-8 text operations unless you intentionally support binary formats.

## Example module

An example plugin module is available at `sample_postprocess_plugins.py`.

### Redact email addresses

```bash
python transcribe_audio.py /path/to/folder --postprocess-plugin "sample_postprocess_plugins:redact_email_addresses"
```

### Write a plugin audit sidecar

```bash
python transcribe_audio.py /path/to/folder --postprocess-plugin "sample_postprocess_plugins:write_plugin_audit"
```

Both examples are intentionally simple and safe for local development.
