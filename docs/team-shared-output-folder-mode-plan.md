# Shared output folder mode with provenance metadata

**Created:** 2026-03-03-17-23
**Last Updated:** 2026-03-03-17-23

Purpose: support a collaborative workflow where multiple projects write to one
centralized transcript repository while keeping strict per-job provenance.

## Current behavior target

- Preserve existing per-project default output behavior.
- Only activate shared-output mode when explicitly configured.
- Keep write order and resume semantics stable for each source directory.

## Desired behavior

When `shared_output.enabled` is `true`:

1. All generated artifacts are written under a single configurable root (`shared_output.root`).
2. A namespace segment (project identifier) is always prefixed in artifact paths.
3. A run manifest is emitted in the shared root:
   - `runs/<run_id>/run_summary.json`
   - `runs/<run_id>/provenance.jsonl`
4. Existing `.whisperbatch` discovery and metadata sidecars continue to be stored next
   to source outputs for local recovery.

## Data model additions

- `run_id`: deterministic UUIDv7 or timestamp-based namespace for traceability.
- `source_path_hash`: hash of normalized source path for uniqueness.
- `project_key`: explicit project label from `.whisperbatch` (fallback: sanitized basename).
- `operator`: optional identity marker for attribution.
- `client_run_token`: optional caller-provided token for cross-run correlation.

## Safety constraints

- Reject shared-output mode when output root is not writable.
- Reject collisions when two active runs target the same `(project_key, source_file)` path unless overwrite is explicitly set.
- Continue to emit failures and postmortem records for any target write failures.

## Rollout plan

### PR-BV — mode discovery and config contract
- Add `shared_output` config block with explicit schema validation.
- Add dry-run summary rendering.

### PR-BV1 — manifest writes
- Implement manifests and immutable provenance append-only writes.
- Add tests for manifest determinism across reruns.

### PR-BV2 — path translation layer
- Add deterministic namespace/path mapping from local inputs to shared root.
- Enforce no duplicate writes unless overwrite is configured.

### PR-BV3 — resume + skip compatibility
- Ensure `resume` behavior compares local outputs when possible and shared outputs when configured.
- Keep failed item semantics unchanged in `failures` + `postmortem.jsonl`.

## Non-functional concerns

- Keep this mode optional to avoid altering current disk layout expectations.
- Expose opt-in mode via both CLI flag and config key.
- Add clear troubleshooting guidance for permission errors and namespace conflicts.
