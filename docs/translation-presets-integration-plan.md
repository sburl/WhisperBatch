# Multilingual translation preset workflow (one-click profile)

This document prepares Big Vision task 4 (translation profile presets).

## Goal

Provide a predictable one-click route to run common translation workflows from presets
while preserving transcription reproducibility metadata and existing resume behavior.

## Preset configuration shape

- `translation_presets` section in `.whisperbatch`:
  - `name`: unique preset name.
  - `source_language`: optional explicit source language token.
  - `target_language`: required output translation language code.
  - `model`: optional override (for future API-backed translator mode).
  - `output_suffix`: optional suffix appended to output stems.
  - `output_format`: optional format override for translation outputs.

## Runtime behavior target

- Add CLI flag `--translation-preset` that can be set per-run.
- Add config value `translation_preset` for per-directory runs.
- Resolution order:
  1. CLI flag
  2. `.whisperbatch` `translation_preset`
  3. No preset (existing behavior)
- On each file, metadata sidecar should include:
  - resolved translation preset name
  - effective `source_language`, `target_language`, and `model`
  - source checksum and run-id for traceability

## Delivery milestones

### PR-BW-1
- Add schema + validation for preset records.
- Add tests for valid/invalid preset selection and override precedence.

### PR-BW-2
- Add translation preset resolution in path/argument assembly.
- Keep runtime transcript metadata and resume checks compatible.

### PR-BW-3
- Add CLI and docs update for translating output flows and expected post-process naming.

## Operational constraints

- Presets are intentionally disabled when hook-based `postprocess_plugin` is not marked safe for translation mode.
- Preserve current default `--language` semantics when translation is not configured.
- Preserve summary `failures` and `postmortem.jsonl` semantics for translation failures.
