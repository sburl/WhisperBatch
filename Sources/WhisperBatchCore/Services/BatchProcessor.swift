import Foundation
import CoreMedia

public enum BatchState: String, Sendable {
    case idle
    case running
    case paused
    case stopping
}

public enum BatchEvent: Sendable {
    case stateChanged(BatchState)
    case fileStarted(AudioFile.ID)
    case fileProgress(AudioFile.ID, Double)
    case fileCompleted(AudioFile.ID, TranscriptionResult, URL)
    case fileError(AudioFile.ID, String)
    case allComplete(succeeded: Int, failed: Int, elapsed: TimeInterval)
}

/// Sendable snapshot of the per-file inputs BatchProcessor needs. The actor only
/// reads these fields; AudioFile (a main-actor model class) is never sent across
/// the actor boundary -- the view model maps to this value type first.
public struct AudioFileJob: Sendable {
    public let id: UUID
    public let url: URL
    public let modelOverride: WhisperModelType?
    public let includeTimestamps: Bool?
    public let cropStart: TimeInterval?
    public let cropEnd: TimeInterval?

    public init(
        id: UUID,
        url: URL,
        modelOverride: WhisperModelType?,
        includeTimestamps: Bool?,
        cropStart: TimeInterval? = nil,
        cropEnd: TimeInterval? = nil
    ) {
        self.id = id
        self.url = url
        self.modelOverride = modelOverride
        self.includeTimestamps = includeTimestamps
        self.cropStart = cropStart
        self.cropEnd = cropEnd
    }
}

public actor BatchProcessor {
    public private(set) var state: BatchState = .idle
    private var engine = TranscriptionEngine()
    #if !APP_STORE
    // MLX is dev-build only — the App Store build ships whisper.cpp (CPU) as its
    // single engine. Instantiated lazily so we don't allocate it when the user
    // is running the swiftWhisper backend.
    private var _mlxEngine: MLXTranscriptionEngine?
    private var mlxEngine: MLXTranscriptionEngine {
        if let existing = _mlxEngine { return existing }
        let new = MLXTranscriptionEngine()
        _mlxEngine = new
        return new
    }
    #endif
    private var eventContinuation: AsyncStream<BatchEvent>.Continuation?
    private var isPauseRequested = false
    private var isStopRequested = false
    private var currentCancellationToken: CancellationToken?

    /// Create an event stream and start processing the given files.
    public init() {}

    public func process(
        files: [AudioFileJob],
        defaultModel: WhisperModelType,
        defaultFormat: OutputFormat,
        defaultTimestamps: Bool,
        outputDirectory: URL?,
        backend: TranscriptionBackend = .swiftWhisper,
        enhanceAudio: Bool = false,
        hallucinationFilterEnabled: Bool = false,
        silenceSkippingEnabled: Bool = false
    ) -> AsyncStream<BatchEvent> {
        let stream = AsyncStream<BatchEvent> { continuation in
            self.eventContinuation = continuation
        }

        Task {
            await run(
                files: files,
                defaultModel: defaultModel,
                defaultFormat: defaultFormat,
                defaultTimestamps: defaultTimestamps,
                outputDirectory: outputDirectory,
                backend: backend,
                enhanceAudio: enhanceAudio,
                hallucinationFilterEnabled: hallucinationFilterEnabled,
                silenceSkippingEnabled: silenceSkippingEnabled
            )
        }

        return stream
    }

    public func pause() {
        guard state == .running else { return }
        isPauseRequested = true
        state = .paused
        emit(.stateChanged(.paused))
    }

    public func resume() {
        guard state == .paused else { return }
        isPauseRequested = false
        state = .running
        emit(.stateChanged(.running))
    }

    public func stop() {
        guard state == .running || state == .paused else { return }
        isStopRequested = true
        isPauseRequested = false
        currentCancellationToken?.cancel()
        state = .stopping
        emit(.stateChanged(.stopping))
    }

    // MARK: - Private

    private func run(
        files: [AudioFileJob],
        defaultModel: WhisperModelType,
        defaultFormat: OutputFormat,
        defaultTimestamps: Bool,
        outputDirectory: URL?,
        backend: TranscriptionBackend,
        enhanceAudio: Bool,
        hallucinationFilterEnabled: Bool,
        silenceSkippingEnabled: Bool
    ) async {
        state = .running
        isPauseRequested = false
        isStopRequested = false
        emit(.stateChanged(.running))

        let outputAccess = outputDirectory.map { SecurityScopedAccess(url: $0) }
        defer { withExtendedLifetime(outputAccess) {} }
        let startTime = ContinuousClock.now
        var pausedDuration: Duration = .zero
        var succeeded = 0
        var failed = 0

        for file in files {
            // Check stop
            if isStopRequested { break }

            // Handle pause (state already set to .paused in pause())
            if isPauseRequested {
                let pauseStart = ContinuousClock.now
                while isPauseRequested && !isStopRequested {
                    try? await Task.sleep(for: .milliseconds(100))
                }
                pausedDuration += ContinuousClock.now - pauseStart
                if isStopRequested { break }
            }

            let fileModel = file.modelOverride ?? defaultModel
            let fileTimestamps = file.includeTimestamps ?? defaultTimestamps

            // Guard: models that require the MLX backend cannot be used with
            // swiftWhisper — there is no ggml-turbo.bin to load.  Fail fast
            // with a clear error rather than silently hanging on a missing file.
            if fileModel.requiresMLX && backend != .mlxWhisper {
                emit(.fileError(
                    file.id,
                    "\(fileModel.displayName) requires the MLX backend. " +
                    "Switch to MLX Whisper in Settings, or choose a different model."
                ))
                failed += 1
                continue
            }

            emit(.fileStarted(file.id))

            do {
                let segments: [TranscriptionSegment]
                let cancellationToken = CancellationToken()
                currentCancellationToken = cancellationToken
                if isStopRequested {
                    cancellationToken.cancel()
                }

                #if APP_STORE
                // Single offline engine: whisper.cpp (CPU).
                segments = try await transcribeWithWhisperCpp(
                    job: file,
                    model: fileModel,
                    cancellationToken: cancellationToken,
                    enhanceAudio: enhanceAudio,
                    hallucinationFilterEnabled: hallucinationFilterEnabled,
                    silenceSkippingEnabled: silenceSkippingEnabled
                )
                #else
                if backend == .mlxWhisper {
                    if file.hasCrop || enhanceAudio || hallucinationFilterEnabled {
                        throw TranscriptionError.transcriptionFailed(
                            "Crop, audio enhancement, and hallucination filtering are currently available with the whisper.cpp backend."
                        )
                    }
                    let fileID = file.id
                    // MLX path: pass the audio file URL directly; mlx_whisper
                    // handles decoding internally (no PCM conversion needed).
                    segments = try await mlxEngine.transcribe(
                        audioURL: file.url,
                        model: fileModel
                    ) { [weak self] progress in
                        Task { await self?.emit(.fileProgress(fileID, progress)) }
                    }
                } else {
                    segments = try await transcribeWithWhisperCpp(
                        job: file,
                        model: fileModel,
                        cancellationToken: cancellationToken,
                        enhanceAudio: enhanceAudio,
                        hallucinationFilterEnabled: hallucinationFilterEnabled,
                        silenceSkippingEnabled: silenceSkippingEnabled
                    )
                }
                #endif
                currentCancellationToken = nil
                if isStopRequested {
                    throw TranscriptionError.cancelled
                }

                // Render output
                let format = defaultFormat
                let text = OutputRenderer.renderOutputText(
                    segments,
                    format: format,
                    includeTimestamps: fileTimestamps
                )

                let result = TranscriptionResult(text: text, segments: segments)

                // Save output file
                let saveDir = outputDirectory ?? file.url.deletingLastPathComponent()
                let outputURL = OutputRenderer.buildOutputFilePath(
                    directory: saveDir,
                    stem: file.url.deletingPathExtension().lastPathComponent,
                    format: format
                )

                // Start accessing the security-scoped resource so we can write
                // next to the source file when sandboxed.
                let didAccess = BookmarkManager.startAccessing(directoryOf: file.url)
                defer {
                    if didAccess { BookmarkManager.stopAccessing(directoryOf: file.url) }
                }

                try text.write(to: outputURL, atomically: true, encoding: .utf8)

                emit(.fileCompleted(file.id, result, outputURL))
                succeeded += 1
            } catch {
                currentCancellationToken = nil
                emit(.fileError(file.id, error.localizedDescription))
                failed += 1
                if isStopRequested { break }
            }
        }

        let totalElapsed = ContinuousClock.now - startTime - pausedDuration
        let elapsedSeconds = Double(totalElapsed.components.seconds)
            + Double(totalElapsed.components.attoseconds) / 1e18

        state = .idle
        emit(.allComplete(succeeded: succeeded, failed: failed, elapsed: elapsedSeconds))
        eventContinuation?.finish()
        eventContinuation = nil
    }

    /// whisper.cpp (CPU) transcription path — the only engine in the App Store build.
    private func transcribeWithWhisperCpp(
        job: AudioFileJob,
        model: WhisperModelType,
        cancellationToken: CancellationToken,
        enhanceAudio: Bool,
        hallucinationFilterEnabled: Bool,
        silenceSkippingEnabled: Bool
    ) async throws -> [TranscriptionSegment] {
        try await engine.loadModel(model)
        if isStopRequested {
            cancellationToken.cancel()
        }
        let fileID = job.id
        return try await engine.transcribe(
            audioURL: job.url,
            cancellationToken: cancellationToken,
            timeRange: job.timeRange,
            enhanceAudio: enhanceAudio,
            hallucinationFilterEnabled: hallucinationFilterEnabled,
            silenceSkippingEnabled: silenceSkippingEnabled
        ) { [weak self] progress in
            Task { await self?.emit(.fileProgress(fileID, progress)) }
        }
    }

    private func emit(_ event: BatchEvent) {
        eventContinuation?.yield(event)
    }
}

private extension AudioFileJob {
    var hasCrop: Bool {
        guard let cropStart, let cropEnd else { return false }
        return cropEnd > cropStart
    }

    var timeRange: CMTimeRange? {
        guard hasCrop, let cropStart, let cropEnd else { return nil }
        return CMTimeRange(
            start: CMTime(seconds: cropStart, preferredTimescale: 600),
            duration: CMTime(seconds: cropEnd - cropStart, preferredTimescale: 600)
        )
    }
}
