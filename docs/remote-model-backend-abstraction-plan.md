# Remote model backend abstraction plan

**Created:** 2026-03-03-17-23
**Last Updated:** 2026-03-03-17-23

Purpose: prepare Big Vision task 7 (`local whisper + API fallback`).

## Goal

Allow future runtime backends (local FastWhisper, cloud APIs, and future self-hosted engines)
through a minimal compatibility interface while keeping default behavior unchanged.

## Contract proposal

Define a `TranscriptionBackend` interface with:

- `name: str`
- `supports_streaming: bool`
- `supports_word_timestamps: bool`
- `transcribe(file_path: str, *, language: str | None, task: str, **kwargs) -> TranscriptResult`
- `supports_batching: bool`

## Safety and compatibility

- Keep `local` backend as default with current defaults.
- Treat backend selection as immutable per run for resumability.
- Persist backend fingerprint in metadata sidecar.

## Phased rollout

### PR-BZ-1
- Add backend interface module and local backend adapter.
- Keep all current CLI defaults using local adapter.

### PR-BZ-2
- Add backend selection validation in config (`backend`, `backend_config`).
- Validate `backend_config` against backend schema.

### PR-BZ-3
- Add optional `remote` backend stub using deterministic exception semantics (placeholder in this stage).
- Preserve `failures`/`postmortem` mapping for backend-level errors.

## Acceptance criteria

- Existing runs without backend config are identical in output and ordering.
- Backend failures do not silently mutate output formats.
- Unsupported backend values fail fast with explicit guidance.
