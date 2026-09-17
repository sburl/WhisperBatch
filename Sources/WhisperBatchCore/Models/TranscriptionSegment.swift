import Foundation

public struct TranscriptionSegment: Identifiable, Codable, Sendable {
    public let id: UUID
    public let start: Double
    public let end: Double
    public let text: String

    public init(start: Double, end: Double, text: String) {
        self.id = UUID()
        self.start = start
        self.end = end
        self.text = text
    }
}
