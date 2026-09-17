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
        for selection in urls {
            let access = SecurityScopedAccess(url: selection)
            let isDirectory = (try? selection.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
            let candidates: [URL]
            if isDirectory {
                let enumerator = FileManager.default.enumerator(
                    at: selection, includingPropertiesForKeys: [.isRegularFileKey],
                    options: [.skipsHiddenFiles, .skipsPackageDescendants]
                )
                candidates = (enumerator?.allObjects as? [URL] ?? []).filter {
                    (try? $0.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true
                }.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
            } else {
                candidates = [selection]
            }
            for url in candidates {
                guard AudioFile.isSupported(url) else { continue }
                guard !files.contains(where: { $0.url == url }) else { continue }
                let file = AudioFile(url: url)
                file.resourceAccess = access
                do {
                    file.duration = try await FileValidator.validate(url: url)
                    file.status = .pending
                } catch {
                    file.status = .invalid
                    file.errorMessage = error.localizedDescription
                }
                files.append(file)
            }
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
