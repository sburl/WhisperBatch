import Foundation

public struct OutputRenderer {

    // MARK: - Timestamp Formatting

    /// Convert seconds to HH:MM:SS format (floor division, no rounding).
    public static func formatTimestamp(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else {
            return "00:00:00"
        }
        let total = Int(seconds)
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let secs = total % 60
        return String(format: "%02d:%02d:%02d", hours, minutes, secs)
    }

    /// Convert seconds to HH:MM:SS{sep}mmm format for SRT/VTT.
    /// SRT uses comma separator, VTT uses dot.
    public static func formatTimestampWithMillis(_ seconds: Double, separator: String = ",") -> String {
        guard seconds.isFinite, seconds >= 0 else {
            return "00:00:00\(separator)000"
        }
        let totalMs = Int((seconds * 1000).rounded())
        let hours = totalMs / 3_600_000
        let minutes = (totalMs % 3_600_000) / 60_000
        let secs = (totalMs % 60_000) / 1_000
        let millis = totalMs % 1_000
        return String(format: "%02d:%02d:%02d%@%03d", hours, minutes, secs, separator, millis)
    }

    // MARK: - Renderers

    /// Render transcript as plain text (no timestamps).
    public static func renderPlainText(_ segments: [TranscriptionSegment]) -> String {
        segments.map { $0.text.trimmingCharacters(in: .whitespaces) }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespaces)
    }

    /// Render transcript with per-segment timestamps.
    /// Format: [HH:MM:SS --> HH:MM:SS] text
    public static func renderTimestampedText(_ segments: [TranscriptionSegment]) -> String {
        segments.map { segment in
            let start = formatTimestamp(segment.start)
            let end = formatTimestamp(segment.end)
            let text = segment.text.trimmingCharacters(in: .whitespaces)
            return "[\(start) --> \(end)] \(text)"
        }.joined(separator: "\n")
    }

    /// Render transcript in SRT subtitle format.
    public static func renderSRT(_ segments: [TranscriptionSegment]) -> String {
        var lines: [String] = []
        for (index, segment) in segments.enumerated() {
            lines.append("\(index + 1)")
            let start = formatTimestampWithMillis(segment.start, separator: ",")
            let end = formatTimestampWithMillis(segment.end, separator: ",")
            lines.append("\(start) --> \(end)")
            lines.append((segment.text).trimmingCharacters(in: .whitespaces))
            lines.append("")
        }
        // Remove trailing empty line to match Python behavior (.rstrip())
        while lines.last == "" { lines.removeLast() }
        return lines.joined(separator: "\n")
    }

    /// Render transcript in WebVTT subtitle format.
    public static func renderVTT(_ segments: [TranscriptionSegment]) -> String {
        var lines: [String] = ["WEBVTT", ""]
        for segment in segments {
            let start = formatTimestampWithMillis(segment.start, separator: ".")
            let end = formatTimestampWithMillis(segment.end, separator: ".")
            lines.append("\(start) --> \(end)")
            lines.append((segment.text).trimmingCharacters(in: .whitespaces))
            lines.append("")
        }
        while lines.last == "" { lines.removeLast() }
        return lines.joined(separator: "\n")
    }

    /// Build a JSON-serializable transcript payload.
    public static func resultToJSONPayload(_ segments: [TranscriptionSegment]) -> [String: Any] {
        let text = segments.map { ($0.text).trimmingCharacters(in: .whitespaces) }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespaces)
        let segs: [[String: Any]] = segments.map { s in
            [
                "start": s.start,
                "end": s.end,
                "text": s.text.trimmingCharacters(in: .whitespaces),
            ]
        }
        return ["text": text, "segments": segs]
    }

    /// Render segments as a JSON string.
    public static func renderJSON(_ segments: [TranscriptionSegment]) -> String {
        // Use Codable for cleaner JSON output
        let payload = JSONPayload(segments: segments)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(payload),
              let json = String(data: data, encoding: .utf8) else {
            return "{}"
        }
        return json
    }

    /// Master dispatcher: render segments into the requested output format.
    public static func renderOutputText(
        _ segments: [TranscriptionSegment],
        format: OutputFormat,
        includeTimestamps: Bool = true
    ) -> String {
        switch format {
        case .txt:
            return includeTimestamps ? renderTimestampedText(segments) : renderPlainText(segments)
        case .srt:
            return renderSRT(segments)
        case .vtt:
            return renderVTT(segments)
        case .json:
            return renderJSON(segments)
        }
    }

    // MARK: - Collision-Safe Output Paths

    /// Build an output file path with collision-safe suffix.
    /// First file: `{stem}_transcription.{ext}`
    /// Subsequent: `{stem}_transcription_2.{ext}`, `{stem}_transcription_3.{ext}`, etc.
    public static func buildOutputFilePath(
        directory: URL,
        stem: String,
        format: OutputFormat
    ) -> URL {
        let ext = format.rawValue
        let base = "\(stem)_transcription"
        let first = directory.appendingPathComponent("\(base).\(ext)")
        guard FileManager.default.fileExists(atPath: first.path) else { return first }

        for i in 2...999 {
            let candidate = directory.appendingPathComponent("\(base)_\(i).\(ext)")
            if !FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
        }
        return first // fallback
    }

    public static func buildOutputFilePath(
        directory: URL,
        stem: String,
        format: OutputFormat,
        occurrence: Int
    ) -> URL {
        let ext = format.rawValue
        let base = "\(stem)_transcription"
        if occurrence <= 1 {
            return directory.appendingPathComponent("\(base).\(ext)")
        }
        return directory.appendingPathComponent("\(base)_\(occurrence).\(ext)")
    }
}

// MARK: - Codable JSON Payload

private struct JSONPayload: Encodable {
    let text: String
    let segments: [JSONSegment]

    init(segments: [TranscriptionSegment]) {
        let segs = segments.map { s in
            JSONSegment(
                start: s.start,
                end: s.end,
                text: s.text.trimmingCharacters(in: .whitespaces)
            )
        }
        self.text = segs.map(\.text).joined(separator: " ").trimmingCharacters(in: .whitespaces)
        self.segments = segs
    }

    struct JSONSegment: Encodable {
        let start: Double
        let end: Double
        let text: String
    }
}
