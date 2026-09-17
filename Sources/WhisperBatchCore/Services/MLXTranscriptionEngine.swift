import Foundation

// The MLX/Metal engine shells out to a user-installed Python (`mlx-whisper`),
// which a sandboxed App Store app cannot launch. The entire engine is therefore
// compiled out of the App Store build — the shipped app has a single offline
// engine (whisper.cpp). This file is dev-build only.
#if !APP_STORE

// MARK: - MLXTranscriptionEngine
//
// Transcribes audio by shelling out to the `mlx_whisper` Python CLI, which
// runs on Apple Silicon via the MLX framework (Metal / Neural Engine).
//
// Prerequisites (not managed here — user installs once):
//   pip install mlx-whisper
//
// mlx_whisper auto-downloads model weights from HuggingFace on first use.
//
// CLI invocation (via the documented console-script entry point
// `mlx_whisper.cli:main`, since upstream does not reliably ship a
// `__main__.py` for `-m mlx_whisper`):
//   python3 -c "from mlx_whisper.cli import main; main()" <audio-file> \
//     --model <hf-repo-id> \
//     --output-format txt \
//     --output-dir <dir>
//
// We capture progress by watching the process stdout for segment lines of the
// form:  [HH:MM:SS.mmm --> HH:MM:SS.mmm]  text…
// which mlx_whisper prints as it decodes each segment.

public final class MLXTranscriptionEngine: @unchecked Sendable {

    // MARK: - Public API

    /// Transcribe `audioURL` using mlx-whisper with `model`.
    /// Reports per-segment progress via `onProgress` (0.0 – 1.0, estimated).
    /// Returns segments suitable for `OutputRenderer`.
    public init() {}

    public func transcribe(
        audioURL: URL,
        model: WhisperModelType,
        progress onProgress: (@Sendable (Double) -> Void)? = nil
    ) async throws -> [TranscriptionSegment] {
        // Locate the Python interpreter that has mlx_whisper installed.
        let python = try await resolvePython()

        // Ask mlx_whisper to write a plain-text + SRT output to a temp dir,
        // then we parse the SRT for timestamps.  We capture stdout live for
        // real-time segment progress.
        let tmpDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("mlx_whisper_\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tmpDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tmpDir) }

        // Invoke mlx-whisper through its documented console-script entry point
        // (`mlx_whisper = mlx_whisper.cli:main`) rather than `python -m
        // mlx_whisper`. Upstream only declares the console script and does not
        // reliably ship a `__main__.py`, so `-m mlx_whisper` can fail at runtime
        // even after a successful `pip install mlx-whisper`. Running
        // `python -c "from mlx_whisper.cli import main; main()" <args>` puts our
        // arguments into sys.argv[1:] exactly as `-m` would, so the CLI's own
        // argparse sees an identical argument vector — only the launch
        // mechanism changes.
        let args = [
            python, "-c", "from mlx_whisper.cli import main; main()",
            audioURL.path,
            "--model", model.mlxRepoID,
            "--output-format", "srt",
            "--output-dir", tmpDir.path,
        ]

        let segments = try await runAndParse(
            args: args,
            tmpDir: tmpDir,
            audioURL: audioURL,
            onProgress: onProgress
        )
        return segments
    }

    // MARK: - Private helpers

    /// Find a Python 3 that has mlx_whisper importable.
    private func resolvePython() async throws -> String {
        // Prefer a venv or conda python that has mlx_whisper.
        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
            "python3",
        ]
        for candidate in candidates {
            let checkArgs = [candidate, "-c", "import mlx_whisper"]
            if (try? await runQuiet(args: checkArgs)) == true {
                return candidate
            }
        }
        throw MLXError.mlxWhisperNotInstalled
    }

    /// Run a process silently; return true if exit code 0.
    private func runQuiet(args: [String]) async throws -> Bool {
        return try await withCheckedThrowingContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = args
            process.standardOutput = FileHandle.nullDevice
            process.standardError  = FileHandle.nullDevice
            process.terminationHandler = { p in
                continuation.resume(returning: p.terminationStatus == 0)
            }
            do {
                try process.run()
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    /// Run mlx_whisper, stream stdout for live progress, then parse the SRT
    /// output file for structured segments.
    private func runAndParse(
        args: [String],
        tmpDir: URL,
        audioURL: URL,
        onProgress: (@Sendable (Double) -> Void)?
    ) async throws -> [TranscriptionSegment] {
        return try await withCheckedThrowingContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = args

            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()
            process.standardOutput = stdoutPipe
            process.standardError  = stderrPipe

            // Thread-safe mutable state captured by the readability handler.
            let state = ProcessState()

            // Drain stderr concurrently. mlx_whisper can be noisy (progress bars,
            // warnings), and if we only read stderr at termination the OS pipe
            // buffer (~64 KB) can fill and block the child process, deadlocking
            // the whole transcription. Accumulate it on a background readability
            // handler so the buffer never fills.
            stderrPipe.fileHandleForReading.readabilityHandler = { handle in
                let chunk = handle.availableData
                guard !chunk.isEmpty else { return }
                state.appendStderr(chunk)
            }

            stdoutPipe.fileHandleForReading.readabilityHandler = { handle in
                let chunk = handle.availableData
                guard !chunk.isEmpty else { return }
                state.append(chunk)
                // Count lines that look like SRT segment timestamps.
                let text = String(decoding: chunk, as: UTF8.self)
                let newSegments = text.components(separatedBy: "\n")
                    .filter { $0.contains(" --> ") }.count
                if newSegments > 0 {
                    let count = state.incrementSegments(by: newSegments)
                    // Progress is speculative: we do not know the total number
                    // of segments up-front, so we use a smoothed asymptote:
                    //   progress = count / (count + k)
                    // where k is a "lookahead" constant that controls pacing.
                    // k=20 gives reasonable UX: the bar reaches 50% at 20 segments
                    // and ~80% at 80 segments, staying honest on long files.
                    // We cap at 0.95 to leave room for the final SRT-parse step.
                    let k = 20.0
                    let smoothed = min(0.95, Double(count) / (Double(count) + k))
                    onProgress?(smoothed)
                }
            }

            process.terminationHandler = { [stdoutPipe, stderrPipe] p in
                // Stop readability handlers before reading final data.
                stdoutPipe.fileHandleForReading.readabilityHandler = nil
                stderrPipe.fileHandleForReading.readabilityHandler = nil

                // Capture any bytes that arrived between the last handler call
                // and termination, then fold them into the accumulated buffer.
                // We never call readDataToEndOfFile() on a pipe we've been
                // draining concurrently — the bulk was already read by the
                // readability handler, so this only mops up the tail.
                let tail = stderrPipe.fileHandleForReading.availableData
                if !tail.isEmpty { state.appendStderr(tail) }

                guard p.terminationStatus == 0 else {
                    let errText = String(decoding: state.stderrData, as: UTF8.self)
                    continuation.resume(
                        throwing: MLXError.processFailed(
                            exitCode: p.terminationStatus,
                            stderr: errText
                        )
                    )
                    return
                }

                // Find the .srt file mlx_whisper wrote.
                let stem = audioURL.deletingPathExtension().lastPathComponent
                let srtURL = tmpDir.appendingPathComponent(stem + ".srt")

                do {
                    let srtText = try String(contentsOf: srtURL, encoding: .utf8)
                    let segments = parseSRT(srtText)
                    onProgress?(1.0)
                    continuation.resume(returning: segments)
                } catch {
                    // Fall back: return a single segment from collected stdout.
                    let raw = String(decoding: state.stdoutData, as: UTF8.self)
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    onProgress?(1.0)
                    if raw.isEmpty {
                        continuation.resume(throwing: MLXError.noOutputProduced)
                    } else {
                        continuation.resume(returning: [
                            TranscriptionSegment(start: 0, end: 0, text: raw)
                        ])
                    }
                }
            }

            do {
                try process.run()
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }
}

// MARK: - Thread-safe state container

/// Accumulates stdout bytes and segment count from a `readabilityHandler`
/// closure, which runs on an arbitrary thread.
final class ProcessState: @unchecked Sendable {
    private let lock = NSLock()
    private var _stdoutData = Data()
    private var _stderrData = Data()
    private var _segmentCount = 0

    var stdoutData: Data {
        lock.withLock { _stdoutData }
    }

    var stderrData: Data {
        lock.withLock { _stderrData }
    }

    func append(_ data: Data) {
        lock.withLock { _stdoutData.append(data) }
    }

    func appendStderr(_ data: Data) {
        lock.withLock { _stderrData.append(data) }
    }

    /// Increments segment count and returns the new total.
    @discardableResult
    func incrementSegments(by n: Int) -> Int {
        lock.withLock {
            _segmentCount += n
            return _segmentCount
        }
    }
}

// MARK: - SRT parser

/// Parse an SRT file into TranscriptionSegments.
private func parseSRT(_ text: String) -> [TranscriptionSegment] {
    // SRT blocks are separated by blank lines.
    // Each block:
    //   <index>
    //   HH:MM:SS,mmm --> HH:MM:SS,mmm
    //   <text lines…>
    var segments: [TranscriptionSegment] = []
    let blocks = text.components(separatedBy: "\n\n")
    for block in blocks {
        let lines = block.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        guard lines.count >= 2 else { continue }
        // The timecode line contains " --> "
        guard let timeLine = lines.first(where: { $0.contains(" --> ") }) else { continue }
        let parts = timeLine.components(separatedBy: " --> ")
        guard parts.count == 2,
              let start = parseSRTTime(parts[0]),
              let end   = parseSRTTime(parts[1]) else { continue }
        // Text is everything after the timecode line.
        let timeLineIndex = lines.firstIndex(where: { $0.contains(" --> ") })!
        let textLines = lines[(timeLineIndex + 1)...]
        let text = textLines.joined(separator: " ")
        guard !text.isEmpty else { continue }
        segments.append(TranscriptionSegment(start: start, end: end, text: text))
    }
    return segments
}

/// Parse "HH:MM:SS,mmm" (SRT) or "HH:MM:SS.mmm" (VTT) → seconds.
private func parseSRTTime(_ s: String) -> Double? {
    let normalised = s.replacingOccurrences(of: ",", with: ".")
    let parts = normalised.components(separatedBy: ":")
    guard parts.count == 3,
          let h  = Double(parts[0]),
          let m  = Double(parts[1]),
          let sec = Double(parts[2]) else { return nil }
    return h * 3600 + m * 60 + sec
}

// MARK: - Error types

public enum MLXError: LocalizedError {
    case mlxWhisperNotInstalled
    case processFailed(exitCode: Int32, stderr: String)
    case noOutputProduced

    public var errorDescription: String? {
        switch self {
        case .mlxWhisperNotInstalled:
            return "mlx-whisper is not installed. Run: pip install mlx-whisper"
        case .processFailed(let code, let stderr):
            let detail = stderr.isEmpty ? "(no stderr)" : stderr.prefix(300).description
            return "mlx_whisper exited with code \(code): \(detail)"
        case .noOutputProduced:
            return "mlx_whisper produced no output."
        }
    }
}

#endif
