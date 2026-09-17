import Foundation

// MARK: - Backend selection

public enum TranscriptionBackend: String, CaseIterable, Identifiable, Codable, Sendable {
    /// whisper.cpp via SwiftWhisper — original cross-platform backend.
    case swiftWhisper = "swiftWhisper"
    /// mlx-whisper running on Apple Silicon GPU/Neural Engine via Metal.
    case mlxWhisper = "mlxWhisper"

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .swiftWhisper: "whisper.cpp (CPU)"
        case .mlxWhisper:   "mlx-whisper (Metal / Apple Silicon)"
        }
    }
}

// MARK: -

@MainActor @Observable
public final class AppSettings {
    public static let shared = AppSettings()

    public var defaultModel: WhisperModelType {
        get {
            guard let raw = UserDefaults.standard.string(forKey: "defaultModel"),
                  let model = WhisperModelType(rawValue: raw) else {
                return .largeV3Turbo
            }
            return model
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "defaultModel") }
    }

    public var defaultOutputFormat: OutputFormat {
        get {
            guard let raw = UserDefaults.standard.string(forKey: "defaultOutputFormat"),
                  let fmt = OutputFormat(rawValue: raw) else {
                return .txt
            }
            return fmt
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "defaultOutputFormat") }
    }

    public var includeTimestamps: Bool {
        get {
            if UserDefaults.standard.object(forKey: "includeTimestamps") == nil {
                return false
            }
            return UserDefaults.standard.bool(forKey: "includeTimestamps")
        }
        set { UserDefaults.standard.set(newValue, forKey: "includeTimestamps") }
    }

    /// nil means "save next to source file"
    public var customOutputDirectory: URL? {
        get {
            guard let bookmark = UserDefaults.standard.data(forKey: "outputDirectoryBookmark") else {
                return nil
            }
            var isStale = false
            guard let url = try? URL(resolvingBookmarkData: bookmark, options: .withSecurityScope, bookmarkDataIsStale: &isStale) else {
                return nil
            }
            if isStale {
                // Re-save bookmark
                if let newBookmark = try? url.bookmarkData(options: .withSecurityScope) {
                    UserDefaults.standard.set(newBookmark, forKey: "outputDirectoryBookmark")
                }
            }
            return url
        }
        set {
            if let url = newValue {
                let bookmark = try? url.bookmarkData(options: .withSecurityScope)
                UserDefaults.standard.set(bookmark, forKey: "outputDirectoryBookmark")
            } else {
                UserDefaults.standard.removeObject(forKey: "outputDirectoryBookmark")
            }
        }
    }

    public var saveNextToSource: Bool {
        customOutputDirectory == nil
    }

    public var transcriptionBackend: TranscriptionBackend {
        get {
            guard let raw = UserDefaults.standard.string(forKey: "transcriptionBackend"),
                  let backend = TranscriptionBackend(rawValue: raw) else {
                return .swiftWhisper
            }
            return backend
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "transcriptionBackend") }
    }

    public var silenceSkippingEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: "silenceSkippingEnabled") }
        set { UserDefaults.standard.set(newValue, forKey: "silenceSkippingEnabled") }
    }

    public var enhanceAudio: Bool {
        get { UserDefaults.standard.bool(forKey: "enhanceAudio") }
        set { UserDefaults.standard.set(newValue, forKey: "enhanceAudio") }
    }

    public var hallucinationFilterEnabled: Bool {
        // Default ON: whisper hallucinates noise-only tokens and repeated-segment
        // loops on silence; the (conservative) filter cleans that up safely.
        get {
            if UserDefaults.standard.object(forKey: "hallucinationFilterEnabled") == nil {
                return true
            }
            return UserDefaults.standard.bool(forKey: "hallucinationFilterEnabled")
        }
        set { UserDefaults.standard.set(newValue, forKey: "hallucinationFilterEnabled") }
    }

    private init() {}
}

public enum OutputFormat: String, CaseIterable, Identifiable, Sendable {
    case txt
    case srt
    case vtt
    case json

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .txt:  "Plain Text (.txt)"
        case .srt:  "Subtitles (.srt)"
        case .vtt:  "Web Captions (.vtt)"
        case .json: "Data (.json)"
        }
    }

    /// One-line plain-language description of what the format is for.
    public var formatDescription: String {
        switch self {
        case .txt:  "Just the words, no timing."
        case .srt:  "Subtitle file with timestamps, for video."
        case .vtt:  "Web video captions with timestamps."
        case .json: "Structured data with per-segment timestamps."
        }
    }

    /// Whether this format always includes timestamps regardless of user preference.
    public var forcesTimestamps: Bool {
        self == .srt || self == .vtt
    }
}
