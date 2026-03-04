# WhisperBatch - Initial Understanding and Question Set

Date: 2026-03-03

## 1) What I understand about this repo (so far)

The repo appears to be a two-part transcription tool:

- `whisper_batch_core/`: reusable Python transcription primitives around `faster-whisper`.
  - loads and caches models
  - transcribes a single file into segment objects
  - renders text with or without timestamps
  - exports constants used by both CLI and GUI.
- `transcribe_audio.py`: simple headless CLI entrypoint for directory batch processing.
- `transcribe_gui.py`: Tkinter-based queue-based GUI with pause/resume/stop, per-file model and timestamp options, drag-and-drop queue reordering, and on-disk output.
- `setup.sh`: environment bootstrap script with Apple-Silicon compatibility checks.
- Packaging metadata: minimal `pyproject.toml` and pinned `requirements.txt`.

Current project health indicators:

- Functionality is concentrated and workable, but concerns are coupled in large files (especially the GUI).
- No test suite exists.
- No GitHub workflow is configured in `.github/workflows`; only Dependabot is present.
- Open dependency bump PRs exist but are currently blocked.
- A recent merged PR expanded supported media extensions and surfaced that core type/constants should be shared across CLI+GUI.

## 2) Inferred objectives (from your request + code)

- Clean up and stabilize architecture (reduce “spaghetti,” improve readability).
- Keep momentum and maintainability high.
- Use many small, tightly scoped PRs.
- Treat open PRs seriously as part of repo improvement.
- Do deep, repeated assessments in cycles (bug behavior, security, CI, dead code, simplification).
- Keep a strict staged roadmap (minimum 5, max 15 tasks/stage).

yes these are all right.

## 3) Assumptions I’m using unless you correct them

- This tool is primarily for local batch transcription on desktop plus CLI automation.

Yes, that's right.

- Core behavior should stay compatible with Apple Silicon/Mac workflows.

Yes, that's right.

- Backward compatibility with existing file/CLI behavior is preferred unless we explicitly deprecate it.

No. Backward compatibility is not a requirement. We can make breaking changes when they reduce long-term complexity.

- No external DB/service is intended for MVP; local files are source/output target.

Yes, that's right.

- Local compute may be slow, so reliability and recoverability matter more than raw speed.

Yes, that's right.

## 4) Questions and decision points (answer before Stage 4 starts, unless you want me to assume defaults)

1. Product scope
   - Primary user: power users, casual users, or both?
   - Should the app be local-only forever, or should API/transmission features be added later?
   - Is multilingual transcription accuracy a current priority versus speed?

I'll be more on the power user, but also just people who are privacy conscious who want to do transcription locally.I don't think we'd ever do API like this. This is just a local thing that someone can run and have a private way to transcribe things and not send their data to a model company.Multilingual is a good goal. I think it could be auto-detected. I gave it some Chinese recordings, and it seemed like it did fine there. We could make it more explicit though.

2. Delivery scope
   - Is there a hard scope freeze this cycle, or is a broad experimental phase acceptable?

You can be really experimental with this. I'm curious what ideas you have to take it forward.

   - Which platforms must remain first-class: macOS, Linux, Windows?

   Mac OS only for now, but in the really late stages you could make it Windows or Linux eventually.

   - Is Linux audio back-end behavior equal priority to macOS?

No, just make this Mac OS.

3. Quality and behavior
   - Should partial/failed files halt the queue, skip gracefully, or create retry queues?

I think retry would be good to incorporate. I don't think you should halt, right? A user is going to give you a giant list of things to do, and you should just do them and you should fail elegantly.

   - Should there be deterministic model download + cache management UI/CLI behavior?

You don't understand what this means. I think that you should just pick and make a decision here.

- Should output format be only text file today, or do you want structured outputs (JSON/CSV/SRT/VTT)?

Text-only output is okay for now, but we can add structured exports (JSON/SRT/VTT) as productized feature work where useful.

4. Security and trust
   - Are local file permissions and credential hygiene currently part of the threat model?

The user is going to run this on their own computer as a Python app. I wouldn't get too worried about it.

   - Should we treat local model cache and output directories as sensitive or just normal app state?

   I don't think it's that big of a deal. People are going to use private stuff on this, but it's all gonna stay on their computer.

5. Maintenance and workflow
   - Do you want to keep pinned exact versions (`==`) or loosen them with constraints?
   - Are you okay with raising Python floor to 3.9+ if needed by a dependency?
   - Should every change ship behind a visible changelog entry and migration note?

   No, we don't need backwards compatibility. Just use whatever you think is best. The floor can get raised, etc.None of the things we do here are going to be long-running, so I don't think you even need any dependency notes. You can have changelog entries, but there's nothing that needs to migrate ever. There's no database or anything.

6. CI and testing policy
   - Is “nightly” allowed to be GitHub-hosted and expensive, or should it be lightweight plus scheduled smoke checks only?

Nightly can be more expensive. It can be GitHub-based. I would eventually like to move CLIs away from GitHub because they're too expensive.

   - Do you want GUI smoke tests in CI, or only unit/integration for core first?

In an ideal world, I think we'd have a go/no-go smoke test, but let's build up to that. I'm sure there's a lot of other stuff to test first.

7. UX direction for GUI
   - Is current Tkinter stack acceptable, or should we plan migration to a web/app wrapper later?

Do a dedicated Mac application later. I think that would be nice for non-technical users, so we could actually distribute this and publish it on a product hunt or something. That's really medium to high priority.

   - Is per-file model override essential to preserve now?

Really, I think the users usually use the same model to process stuff.

## 5) Open issues I will track while working

- No GitHub workflow exists today; CI is not currently enforcing tests.
- No test harness is present, so regression safety is low.
- Error handling is present but inconsistent across CLI and GUI.
- Some architecture is coupled (GUI does command execution, validation, timing, rendering, and model orchestration in one file).
- `requirements.txt` is pinned and likely outdated on some packages.
- `whisper_batch_core` APIs are thin but can be hardened with validation and richer output metadata.

## 6) If you do not answer these now

I will use conservative defaults above and mark each assumption explicitly in the plan docs so you can adjust stage-by-stage without losing momentum.

## 7) Resolved direction from your latest answers

1. Build for local-first, private processing only; no API/service integration.
2. Primary platform is macOS in this cycle; Linux and Windows are not a priority now.
3. Retry-on-error behavior should be graceful: failed files are recorded and queue continues.
4. No compatibility constraints required unless you explicitly ask for them.
5. Python version floor can be raised as needed by dependency strategy.
6. No migration policy is required per change unless behavior changes materially.
7. CI can be more expensive on scheduled/nightly runs.
8. Keep Tkinter for now; plan dedicated Mac app packaging as a medium/high priority future goal.
