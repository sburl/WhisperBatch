import Foundation

/// Keeps the user-selected file or folder accessible for the lifetime of a job.
public final class SecurityScopedAccess: Sendable {
    public let url: URL
    private let didAccess: Bool

    public init(url: URL) {
        self.url = url
        self.didAccess = url.startAccessingSecurityScopedResource()
    }

    deinit {
        if didAccess { url.stopAccessingSecurityScopedResource() }
    }
}
