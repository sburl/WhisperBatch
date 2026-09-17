import Foundation
import UniformTypeIdentifiers

public enum AudioFileStatus: String, Sendable {
    case pending = "Pending"
    case processing = "Processing"
    case complete = "Complete"
    case error = "Error"
    case invalid = "Invalid"
    case notAccessible = "Not Accessible"
}

@Observable
public final class AudioFile: Identifiable {
    public let id: UUID
    public let url: URL
    public var resourceAccess: SecurityScopedAccess?
    public let filename: String
    public var duration: TimeInterval?
    public var status: AudioFileStatus
    public var errorMessage: String?
    public var modelOverride: WhisperModelType?
    public var includeTimestamps: Bool?
    public var progress: Double
    public var outputURL: URL?
    public var cropStart: TimeInterval?
    public var cropEnd: TimeInterval?

    public init(url: URL, duration: TimeInterval? = nil) {
        self.id = UUID()
        self.url = url
        self.filename = url.lastPathComponent
        self.duration = duration
        self.status = .pending
        self.progress = 0
    }

    public static let supportedExtensions: Set<String> = [
        // Audio
        "aac", "aiff", "alac", "flac", "m4a", "mp3",
        "ogg", "opus", "wav",
        // Video
        "3gp", "avi", "flv", "m4v", "mkv", "mov", "mp4",
        "mpeg", "mpg", "ts", "webm", "wmv",
    ]

    public static let supportedContentTypes: [UTType] = [
        .audio, .movie, .mpeg4Audio, .mp3, .wav, .aiff,
    ]

    public var hasCrop: Bool {
        guard let cropStart, let cropEnd else { return false }
        return cropEnd > cropStart
    }

    public static func isSupported(_ url: URL) -> Bool {
        supportedExtensions.contains(url.pathExtension.lowercased())
    }
}
