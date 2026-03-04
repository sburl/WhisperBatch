# Speaker segmentation and optional speaker tagging prototype

Purpose: define a small scoped path to Big Vision task 6.

## Immediate intent

Add optional speaker-aware transcript mode with deterministic segment attribution and low-risk runtime guardrails.

## Execution strategy

1. Add a `speaker_segmentation` config block:
   - `enabled` (bool, default false)
   - `engine` (`whisper`, `pyannote`, `fallback`) as plugin-selectable enum
   - `min_speaker_confidence` (float)
   - `output_style` (`inline`, `inline-with-labels`, `speaker-only`)
2. Introduce speaker metadata in output:
   - segment fields: `speaker_id`, `speaker_name` (optional), `speaker_confidence`.
3. Keep default output format unchanged when disabled.

## Rollout milestones

### PR-BY-1
- Add config parsing + validation.
- Add schema checks and tests for invalid options.

### PR-BY-2
- Add optional speaker-aware post-processing path behind strict feature gate.
- Preserve deterministic output ordering with stable speaker label assignment.

### PR-BY-3
- Add CLI docs and README examples for shared mode and fallback when segmentation engine is unavailable.

## Risk controls

- No external speaker model downloads unless user enables speaker mode.
- Explicitly disable speaker mode on unsupported file formats and single-speaker test sets.
- Maintain failure mapping to `failures` and `postmortem.jsonl`.
