import Foundation

/// Manages security-scoped bookmarks so the sandboxed app can regain access
/// to user-selected directories across launches.
public enum BookmarkManager {

    /// In-memory cache: directory path -> bookmark Data.
    /// Not persisted to disk for now; bookmarks are re-created each session
    /// when files are added via the file importer or drag-drop.
    nonisolated(unsafe) private static var bookmarks: [String: Data] = [:]

    // MARK: - Save

    /// Save a security-scoped bookmark for the parent directory of the given URL.
    public static func saveBookmark(for url: URL) {
        let directory = url.deletingLastPathComponent()
        let key = directory.path

        // Don't duplicate work
        guard bookmarks[key] == nil else { return }

        do {
            let bookmarkData = try directory.bookmarkData(
                options: .withSecurityScope,
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            bookmarks[key] = bookmarkData
        } catch {
            // Best-effort; if bookmarking fails we still have the temporary
            // sandbox grant for the current session.
            print("BookmarkManager: failed to create bookmark for \(key): \(error)")
        }
    }

    // MARK: - Access

    /// Resolve the bookmark for a directory and start accessing the
    /// security-scoped resource.  Returns `true` if access was started
    /// (caller must call `stopAccessing` when done).
    @discardableResult
    public static func startAccessing(directoryOf url: URL) -> Bool {
        let directory = url.deletingLastPathComponent()
        let key = directory.path

        guard let data = bookmarks[key] else { return false }

        var isStale = false
        do {
            let resolved = try URL(
                resolvingBookmarkData: data,
                options: .withSecurityScope,
                relativeTo: nil,
                bookmarkDataIsStale: &isStale
            )

            if isStale {
                // Re-create the bookmark with the resolved URL
                if let fresh = try? resolved.bookmarkData(
                    options: .withSecurityScope,
                    includingResourceValuesForKeys: nil,
                    relativeTo: nil
                ) {
                    bookmarks[key] = fresh
                }
            }

            return resolved.startAccessingSecurityScopedResource()
        } catch {
            print("BookmarkManager: failed to resolve bookmark for \(key): \(error)")
            return false
        }
    }

    /// Stop accessing the security-scoped resource for the parent directory
    /// of the given URL.
    public static func stopAccessing(directoryOf url: URL) {
        let directory = url.deletingLastPathComponent()
        directory.stopAccessingSecurityScopedResource()
    }
}
