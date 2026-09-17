import Foundation
import SwiftUI
import WhisperBatchCore

@MainActor @Observable
final class TranscriptionViewModel {
    var batchState: BatchState = .idle
    var currentFileID: AudioFile.ID?
    var overallProgress: Double = 0
    var elapsedTime: TimeInterval = 0
    var transcripts: [TranscriptItem] = []
    var runSummary: String = ""
    var succeededCount = 0
    var failedCount = 0
    var totalFileCount = 0

    struct TranscriptItem: Identifiable {
        let id = UUID()
        let filename: String
        let text: String
        let failed: Bool
    }

    /// ETA based on the transcription rate measured *after* warm-up. Model load
    /// makes the first few seconds' progress-rate wildly unrepresentative (that's
    /// what produced the bogus "4 min" estimate on a 10s job), so we anchor the
    /// rate at the moment real progress begins and extrapolate only from there.
    var estimatedTimeRemaining: TimeInterval? {
        guard let anchor = rateAnchorTime, overallProgress < 0.97 else { return nil }
        let moved = overallProgress - rateAnchorProgress
        guard moved > 0.05 else { return nil }
        let d = ContinuousClock.now - anchor
        let since = Double(d.components.seconds) + Double(d.components.attoseconds) / 1e18
        guard since > 1 else { return nil }
        let remaining = (1 - overallProgress) * (since / moved)
        return remaining > 1 ? remaining : nil
    }

    private var processor = BatchProcessor()
    private var timerTask: Task<Void, Never>?
    private var processingStartTime: ContinuousClock.Instant?
    private var rateAnchorTime: ContinuousClock.Instant?
    private var rateAnchorProgress: Double = 0

    var isRunning: Bool { batchState == .running }
    var isPaused: Bool { batchState == .paused }
    var canStart: Bool { batchState == .idle }
    var canPause: Bool { batchState == .running }
    var canResume: Bool { batchState == .paused }
    var canStop: Bool { batchState == .running || batchState == .paused }

    func start(
        files: [AudioFile],
        model: WhisperModelType,
        format: OutputFormat,
        timestamps: Bool
    ) {
        guard batchState == .idle else { return }

        transcripts = []
        runSummary = "\(model.displayName)   ·   \(format.displayName)   ·   "
            + (timestamps ? "Timestamps on" : "No timestamps")
        succeededCount = 0
        failedCount = 0
        overallProgress = 0
        totalFileCount = files.count
        processingStartTime = .now
        rateAnchorTime = nil
        rateAnchorProgress = 0

        startTimer()

        let outputDir = AppSettings.shared.customOutputDirectory
        let backend = AppSettings.shared.transcriptionBackend
        let enhanceAudio = AppSettings.shared.enhanceAudio
        let hallucinationFilterEnabled = AppSettings.shared.hallucinationFilterEnabled
        let silenceSkippingEnabled = AppSettings.shared.silenceSkippingEnabled
        let eventStream = Task {
            await processor.process(
                files: files.map {
                    AudioFileJob(
                        id: $0.id,
                        url: $0.url,
                        modelOverride: $0.modelOverride,
                        includeTimestamps: $0.includeTimestamps,
                        cropStart: $0.cropStart,
                        cropEnd: $0.cropEnd
                    )
                },
                defaultModel: model,
                defaultFormat: format,
                defaultTimestamps: timestamps,
                outputDirectory: outputDir,
                backend: backend,
                enhanceAudio: enhanceAudio,
                hallucinationFilterEnabled: hallucinationFilterEnabled,
                silenceSkippingEnabled: silenceSkippingEnabled
            )
        }

        Task {
            let stream = await eventStream.value
            let totalFiles = files.count

            for await event in stream {
                await MainActor.run {
                    self.handleEvent(event, totalFiles: totalFiles, files: files)
                }
            }
        }
    }

    func pause() {
        Task { await processor.pause() }
    }

    func resume() {
        Task { await processor.resume() }
    }

    func stop() {
        Task { await processor.stop() }
    }

    // MARK: - Private

    @MainActor
    private func handleEvent(_ event: BatchEvent, totalFiles: Int, files: [AudioFile]) {
        switch event {
        case .stateChanged(let state):
            batchState = state
            if state == .idle {
                stopTimer()
            }

        case .fileStarted(let id):
            currentFileID = id
            if let file = files.first(where: { $0.id == id }) {
                file.status = .processing
                file.progress = 0
            }

        case .fileProgress(let id, let progress):
            if let file = files.first(where: { $0.id == id }) {
                file.progress = progress
            }
            // Overall = completed files + fraction of current file
            let completedFiles = Double(succeededCount + failedCount)
            overallProgress = (completedFiles + progress) / Double(totalFiles)
            anchorRateIfNeeded()

        case .fileCompleted(let id, let result, let outputURL):
            if let file = files.first(where: { $0.id == id }) {
                file.status = .complete
                file.progress = 1.0
                file.outputURL = outputURL
                let body = result.text.trimmingCharacters(in: .whitespacesAndNewlines)
                transcripts.append(TranscriptItem(
                    filename: file.filename,
                    text: body.isEmpty ? "(no speech detected)" : body,
                    failed: false
                ))
            }
            succeededCount += 1
            overallProgress = Double(succeededCount + failedCount) / Double(totalFiles)
            anchorRateIfNeeded()

        case .fileError(let id, let message):
            if let file = files.first(where: { $0.id == id }) {
                file.status = .error
                file.errorMessage = message
                transcripts.append(TranscriptItem(filename: file.filename, text: message, failed: true))
            }
            failedCount += 1
            overallProgress = Double(succeededCount + failedCount) / Double(totalFiles)

        case .allComplete(let succeeded, let failed, let elapsed):
            batchState = .idle
            currentFileID = nil
            // Reset any files still processing/pending back to pending
            for file in files where file.status == .processing {
                file.status = .pending
                file.progress = 0
            }
            stopTimer()
            sendCompletionNotification(succeeded: succeeded, failed: failed)
        }
    }

    private func anchorRateIfNeeded() {
        if rateAnchorTime == nil && overallProgress > 0.02 {
            rateAnchorTime = .now
            rateAnchorProgress = overallProgress
        }
    }

    private func startTimer() {
        timerTask = Task { @MainActor in
            while !Task.isCancelled {
                if let start = processingStartTime {
                    let elapsed = ContinuousClock.now - start
                    elapsedTime = Double(elapsed.components.seconds)
                }
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    private func stopTimer() {
        timerTask?.cancel()
        timerTask = nil
    }

    private func sendCompletionNotification(succeeded: Int, failed: Int) {
        let content = UNMutableNotificationContent()
        content.title = "WhisperBatch Complete"
        content.body = "\(succeeded) files transcribed" + (failed > 0 ? ", \(failed) failed" : "")
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }
}

import UserNotifications
