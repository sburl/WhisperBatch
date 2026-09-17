import CoreMedia
import Foundation
import WhisperKit

public enum TranscriptionError: LocalizedError {
    case modelNotLoaded
    case transcriptionFailed(String)
    case cancelled
    case invalidLanguage(String)

    public var errorDescription: String? {
        switch self {
        case .modelNotLoaded:
            "No model is loaded. Please download and select a model first."
        case .transcriptionFailed(let message):
            "Transcription failed: \(message)"
        case .cancelled:
            "Transcription was cancelled."
        case .invalidLanguage(let language):
            "Invalid language '\(language)'. Use an ISO code such as 'en', or omit for auto-detect."
        }
    }
}

/// WhisperKit-backed transcription engine.
///
/// Replaces the old SwiftWhisper / whisper.cpp engine, whose vendored whisper.cpp
/// was too old and asserted/aborted on large-v3 and large-v3-turbo. WhisperKit runs
/// the official CoreML models on the Neural Engine / GPU, supports turbo natively,
/// and (because it loads CoreML model files rather than spawning anything) is
/// App Store sandbox-safe.
public final class TranscriptionEngine: @unchecked Sendable {
    private var pipe: WhisperKit?
    private var currentModelType: WhisperModelType?
    private var currentLanguage: String?

    public init() {}

    /// Load (downloading on first use) the WhisperKit pipeline for `modelType`.
    /// Reloads only when the model or language changes.
    public func loadModel(_ modelType: WhisperModelType, language: String? = nil) async throws {
        if currentModelType == modelType, currentLanguage == language, pipe != nil { return }

        let config = WhisperKitConfig(
            model: modelType.whisperKitModelName,
            downloadBase: ModelManager.downloadBaseURL,
            verbose: false,
            logLevel: .error,
            prewarm: false,
            load: true,
            download: true
        )
        do {
            pipe = try await WhisperKit(config)
        } catch {
            pipe = nil
            currentModelType = nil
            throw TranscriptionError.transcriptionFailed(
                "Could not load \(modelType.displayName): \(error.localizedDescription)"
            )
        }
        currentModelType = modelType
        currentLanguage = language
    }

    /// Transcribe `audioURL`. WhisperKit loads/decodes the file itself (handles
    /// mp3/m4a/mov/etc. via AVFoundation), so we hand it the path directly.
    public func transcribe(
        audioURL: URL,
        cancellationToken: CancellationToken? = nil,
        timeRange: CMTimeRange? = nil,
        enhanceAudio: Bool = false,
        hallucinationFilterEnabled: Bool = false,
        silenceSkippingEnabled: Bool = false,
        progress: (@Sendable (Double) -> Void)? = nil
    ) async throws -> [TranscriptionSegment] {
        guard let pipe else { throw TranscriptionError.modelNotLoaded }
        if cancellationToken?.isCancelled == true { throw TranscriptionError.cancelled }

        var options = DecodingOptions()
        // Strip Whisper's special/timestamp tokens (<|startoftranscript|>, <|6.16|>, …)
        // from segment text — we render our own timestamps from segment.start/.end.
        options.skipSpecialTokens = true
        if let language = currentLanguage, !language.isEmpty {
            options.language = language
            options.detectLanguage = false
        } else {
            options.detectLanguage = true
        }
        // Skip-silence maps to WhisperKit's built-in VAD chunking.
        if silenceSkippingEnabled {
            options.chunkingStrategy = .vad
        }
        // Crop maps to WhisperKit clip timestamps [start, end] in seconds.
        if let timeRange {
            let start = CMTimeGetSeconds(timeRange.start)
            let dur = CMTimeGetSeconds(timeRange.duration)
            if start.isFinite, dur.isFinite, dur > 0 {
                options.clipTimestamps = [Float(start), Float(start + dur)]
            }
        }
        // NOTE: `enhanceAudio` (band-pass + denoise) is not yet wired into the
        // WhisperKit path — it's a safe no-op for now. WhisperKit's CoreML models
        // are robust to noisy input, so the practical impact is small. TODO: run
        // samples through AudioEnhancer and use transcribe(audioArray:).
        _ = enhanceAudio

        progress?(0.05)
        let callback: TranscriptionCallback = { _ in
            (cancellationToken?.isCancelled == true) ? false : nil
        }

        do {
            // No type annotation here on purpose: the bare names `TranscriptionResult`
            // / `TranscriptionSegment` resolve to OUR module's types and would shadow
            // WhisperKit's. Let inference keep WhisperKit's types for `whisperResults`.
            let whisperResults = try await pipe.transcribe(
                audioPath: audioURL.path,
                decodeOptions: options,
                callback: callback
            )
            if cancellationToken?.isCancelled == true { throw TranscriptionError.cancelled }

            let segments: [TranscriptionSegment] = whisperResults
                .flatMap { $0.segments }
                .map { seg in
                    TranscriptionSegment(
                        start: Double(seg.start),
                        end: Double(seg.end),
                        text: seg.text.trimmingCharacters(in: .whitespaces)
                    )
                }
                .filter { !$0.text.isEmpty }

            progress?(1.0)
            return hallucinationFilterEnabled ? HallucinationFilter.clean(segments) : segments
        } catch let error as TranscriptionError {
            throw error
        } catch {
            if cancellationToken?.isCancelled == true { throw TranscriptionError.cancelled }
            throw TranscriptionError.transcriptionFailed(error.localizedDescription)
        }
    }

    public func unloadModel() {
        pipe = nil
        currentModelType = nil
        currentLanguage = nil
    }
}
