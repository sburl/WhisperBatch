import Foundation
import SwiftUI
import WhisperBatchCore
import UniformTypeIdentifiers

@MainActor @Observable
final class FileQueueViewModel {
    var files: [AudioFile] = []
    var selectedFileIDs: Set<AudioFile.ID> = []
    var showFilePicker = false

    func addFiles(urls: [URL]) async {
        for url in urls {
            guard AudioFile.isSupported(url) else { continue }
            // Avoid duplicates
            guard !files.contains(where: { $0.url == url }) else { continue }

            let file = AudioFile(url: url)

            // Save a security-scoped bookmark for the file's parent directory
            // so we can write output files next to the source when sandboxed.
            BookmarkManager.saveBookmark(for: url)

            // Validate and get duration
            do {
                let duration = try await FileValidator.validate(url: url)
                file.duration = duration
                file.status = .pending
            } catch {
                file.status = .invalid
                file.errorMessage = error.localizedDescription
            }

            files.append(file)
        }
    }

    func removeSelected() {
        files.removeAll { selectedFileIDs.contains($0.id) }
        selectedFileIDs.removeAll()
    }

    func removeAll() {
        files.removeAll()
        selectedFileIDs.removeAll()
    }

    func moveFiles(from source: IndexSet, to destination: Int) {
        files.move(fromOffsets: source, toOffset: destination)
    }

    /// Files that are pending (ready to process).
    var pendingFiles: [AudioFile] {
        files.filter { $0.status == .pending }
    }

    /// Total duration of all files.
    var totalDuration: TimeInterval {
        files.compactMap(\.duration).reduce(0, +)
    }

    /// Total duration of pending files.
    var pendingDuration: TimeInterval {
        pendingFiles.compactMap(\.duration).reduce(0, +)
    }

    /// Handle drop of file URLs.
    func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            if provider.canLoadObject(ofClass: URL.self) {
                _ = provider.loadObject(ofClass: URL.self) { [weak self] url, _ in
                    guard let url else { return }
                    Task { @MainActor in
                        await self?.addFiles(urls: [url])
                    }
                }
            }
        }
        return true
    }
}
