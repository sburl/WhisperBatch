import Foundation
import WhisperKit

public enum ModelDownloadError: LocalizedError {
    case downloadFailed(String)
    case fileOperationFailed(Error)

    public var errorDescription: String? {
        switch self {
        case .downloadFailed(let message):
            "Model download failed: \(message)"
        case .fileOperationFailed(let error):
            "File operation failed: \(error.localizedDescription)"
        }
    }
}

public struct ModelDownloadProgress: Sendable {
    public let model: WhisperModelType
    public let bytesDownloaded: Int64
    public let totalBytes: Int64

    public var fractionCompleted: Double {
        guard totalBytes > 0 else { return 0 }
        return Double(bytesDownloaded) / Double(totalBytes)
    }
}

/// Manages WhisperKit CoreML models on disk.
///
/// WhisperKit downloads its CoreML model variants from the argmaxinc/whisperkit-coreml
/// HuggingFace repo into `<downloadBase>/models/argmaxinc/whisperkit-coreml/<variant>/`.
/// We pin `downloadBase` to Application Support so the app, the download UI, and the
/// engine all share one cache. (The old engine bundled a tiny GGML model for offline
/// first-launch; WhisperKit has no equivalent, so Tiny now downloads on first use
/// like every other model.)
public actor ModelManager {
    public static let shared = ModelManager()

    /// Root folder WhisperKit downloads models into (shared by engine + UI).
    public static let downloadBaseURL: URL = {
        let appSupport = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        return appSupport.appendingPathComponent("WhisperBatch", isDirectory: true)
    }()

    private static let modelRepo = "argmaxinc/whisperkit-coreml"
    private static let repoSubpath = "models/argmaxinc/whisperkit-coreml"

    public init() {}

    private func modelFolderURL(for model: WhisperModelType) -> URL {
        Self.downloadBaseURL
            .appendingPathComponent(Self.repoSubpath, isDirectory: true)
            .appendingPathComponent(model.whisperKitModelName, isDirectory: true)
    }

    public func modelPath(for model: WhisperModelType) -> URL {
        modelFolderURL(for: model)
    }

    public func isModelDownloaded(_ model: WhisperModelType) -> Bool {
        let folder = modelFolderURL(for: model)
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: folder.path, isDirectory: &isDir),
              isDir.boolValue else {
            return false
        }
        // A fully-downloaded WhisperKit model folder contains compiled .mlmodelc
        // bundles and a config. Treat "has a compiled model" as downloaded.
        let contents = (try? FileManager.default.contentsOfDirectory(atPath: folder.path)) ?? []
        return contents.contains { $0.hasSuffix(".mlmodelc") }
    }

    public func downloadedModels() -> [WhisperModelType] {
        WhisperModelType.ggmlDownloadable.filter { isModelDownloaded($0) }
    }

    public func downloadModel(
        _ model: WhisperModelType,
        progress: @Sendable @escaping (ModelDownloadProgress) -> Void
    ) async throws {
        do {
            _ = try await WhisperKit.download(
                variant: model.whisperKitModelName,
                downloadBase: Self.downloadBaseURL,
                from: Self.modelRepo,
                progressCallback: { p in
                    progress(ModelDownloadProgress(
                        model: model,
                        bytesDownloaded: p.completedUnitCount,
                        totalBytes: max(p.totalUnitCount, 1)
                    ))
                }
            )
        } catch {
            throw ModelDownloadError.downloadFailed(error.localizedDescription)
        }
    }

    /// WhisperKit's downloader cleans up after itself; nothing to do.
    public func cleanupPartialDownload(_ model: WhisperModelType) throws {}

    public func deleteModel(_ model: WhisperModelType) throws {
        let folder = modelFolderURL(for: model)
        guard FileManager.default.fileExists(atPath: folder.path) else { return }
        do {
            try FileManager.default.removeItem(at: folder)
        } catch {
            throw ModelDownloadError.fileOperationFailed(error)
        }
    }
}
