import SwiftUI
import WhisperBatchCore

@MainActor @Observable
final class ModelManagerViewModel {
    var models: [ModelInfo] = []
    var downloadingModel: WhisperModelType?
    var downloadProgress: Double = 0
    var errorMessage: String?

    private var downloadTask: Task<Void, Never>?

    struct ModelInfo: Identifiable {
        let type: WhisperModelType
        var isDownloaded: Bool
        var id: String { type.rawValue }
    }

    func refresh() async {
        let manager = ModelManager.shared
        var updatedModels: [ModelInfo] = []
        // Only list GGML-downloadable models here: this view drives the GGML
        // (whisper.cpp) download UI. MLX-only models (e.g. Turbo) have no
        // `ggml-*.bin` and would 404 if offered for download.
        for modelType in WhisperModelType.ggmlDownloadable {
            let downloaded = await manager.isModelDownloaded(modelType)
            updatedModels.append(ModelInfo(type: modelType, isDownloaded: downloaded))
        }
        models = updatedModels
    }

    func download(_ model: WhisperModelType) async {
        guard downloadingModel == nil else { return }
        downloadingModel = model
        downloadProgress = 0
        errorMessage = nil

        downloadTask = Task {
            do {
                try await ModelManager.shared.downloadModel(model) { [weak self] progressInfo in
                    Task { @MainActor in
                        self?.downloadProgress = progressInfo.fractionCompleted
                    }
                }
                await refresh()
            } catch is CancellationError {
                // Clean up partial download
                try? await ModelManager.shared.cleanupPartialDownload(model)
            } catch {
                errorMessage = error.localizedDescription
            }

            downloadingModel = nil
            downloadProgress = 0
        }

        await downloadTask?.value
    }

    func cancelDownload() {
        downloadTask?.cancel()
        downloadTask = nil
    }

    func delete(_ model: WhisperModelType) async {
        errorMessage = nil
        do {
            try await ModelManager.shared.deleteModel(model)
            await refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
