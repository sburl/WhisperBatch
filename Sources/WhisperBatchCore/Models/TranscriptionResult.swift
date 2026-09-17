import Foundation

public struct TranscriptionResult: Sendable {
    public let text: String
    public let segments: [TranscriptionSegment]

    public init(text: String, segments: [TranscriptionSegment]) {
        self.text = text
        self.segments = segments
    }
}
