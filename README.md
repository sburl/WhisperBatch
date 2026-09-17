# WhisperBatch

A native SwiftUI app for batch transcription on macOS 14 and later. Add recordings to a queue, choose a Whisper model, and save transcripts alongside the original files or in a chosen folder. Transcription runs locally through [WhisperKit](https://github.com/argmaxinc/WhisperKit).

## Features

- Batch audio/video files with per-file model and output settings.
- Waveform preview and cropping before transcription.
- Plain text, SRT, VTT, and JSON output; optional timestamps in text.
- Tiny, Small, Large v3 Turbo (the default), and Large v3 models.
- Automatic model downloads on first use, then local transcription using cached models.
- Optional silence skipping and a hallucination filter enabled by default.
- A command-line interface using the same Swift transcription core.

The Swift app supersedes the Python/Tkinter interface. The original app is preserved in [legacy/python](legacy/python), and the historical 1.0.0 release is the Python version.

## Build the Mac app

Requirements: macOS 14+, Xcode with Swift 6+, and [XcodeGen](https://github.com/yonaskolb/XcodeGen). Apple Silicon is recommended for local Core ML inference. Building dependencies and downloading a model initially require internet access.

```sh
brew install xcodegen
git clone https://github.com/sburl/WhisperBatch.git
cd WhisperBatch
./build-local.sh
open build/DerivedData/Build/Products/AppStore/WhisperBatch.app
```

The script creates an ad-hoc-signed local build with the updater disabled. It does not install into `/Applications`. This is a source-build workflow, not a signed and notarized public binary release. Python and a separate FFmpeg installation are not required for the Swift app.

Open the app, add recordings, choose a model, and start transcription. The model downloads on first use. By default, output is plain text saved next to each source file. Settings lets you choose a different output folder and format.

## Command line

```sh
swift run whisperbatch-cli /path/to/recordings
swift run whisperbatch-cli ./interview.m4a --model small --format srt --output ./transcripts
swift run whisperbatch-cli ./recordings --format all --language en
swift run whisperbatch-cli --help
```

The CLI defaults to `large-v3-turbo` and `.txt` output alongside each input. Models download automatically; no separate GGML download is needed.

## Development

```sh
swift build
swift test
```

`Sources/WhisperBatch` contains the SwiftUI interface, `Sources/WhisperBatchCore` the shared engine, and `Sources/WhisperBatchCLI` the CLI. `project.yml` generates the Xcode project. The optional audio enhancement flag is currently a no-op in the WhisperKit engine; it is not an advertised transcription feature. The Sparkle updater is not configured for a public update feed.

The Swift source was migrated from the WhisperBatchApp directory of the author's SmallTools project, including its tests and app resources. See [LICENSE](LICENSE).
