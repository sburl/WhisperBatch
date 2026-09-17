import AVFoundation
import Foundation

public enum FileValidationError: LocalizedError {
    case fileNotFound
    case notAccessible
    case unsupportedFormat
    case invalidDuration
    case avFoundationError(String)

    public var errorDescription: String? {
        switch self {
        case .fileNotFound:
            return "File not found."
        case .notAccessible:
            return "File is not accessible."
        case .unsupportedFormat:
            return "Unsupported file format."
        case .invalidDuration:
            return "File has no valid duration."
        case .avFoundationError(let message):
            return "AVFoundation error: \(message)"
        }
    }
}

public struct FileValidator {
    /// Validate a media file and return its duration.
    public static func validate(url: URL) async throws -> TimeInterval {
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw FileValidationError.fileNotFound
        }

        guard isAccessible(url: url) else {
            throw FileValidationError.notAccessible
        }

        let ext = url.pathExtension.lowercased()
        guard AudioFile.supportedExtensions.contains(ext) else {
            throw FileValidationError.unsupportedFormat
        }

        let asset = AVAsset(url: url)
        let duration: CMTime
        do {
            duration = try await asset.load(.duration)
        } catch {
            throw FileValidationError.avFoundationError(error.localizedDescription)
        }

        let seconds = CMTimeGetSeconds(duration)
        guard seconds > 0, seconds.isFinite else {
            throw FileValidationError.invalidDuration
        }

        return seconds
    }

    /// Quick check if file is readable.
    public static func isAccessible(url: URL) -> Bool {
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            return false
        }
        defer { try? handle.close() }
        let data = handle.readData(ofLength: 1024)
        return !data.isEmpty
    }
}
