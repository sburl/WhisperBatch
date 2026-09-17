import XCTest
@testable import WhisperBatchCore

final class OutputRendererTests: XCTestCase {

    // MARK: - Test Data

    static let sampleSegments: [TranscriptionSegment] = [
        TranscriptionSegment(start: 0.0, end: 2.5, text: "Hello world"),
        TranscriptionSegment(start: 2.5, end: 5.0, text: "Goodbye"),
    ]

    static let singleSegment: [TranscriptionSegment] = [
        TranscriptionSegment(start: 0.0, end: 1.0, text: " Hello "),
    ]

    // MARK: - formatTimestamp

    func testFormatTimestampZero() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(0.0), "00:00:00")
    }

    func testFormatTimestampSimple() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(65.0), "00:01:05")
    }

    func testFormatTimestampWithHours() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(3661.0), "01:01:01")
    }

    func testFormatTimestampFloors() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(59.999), "00:00:59")
    }

    func testFormatTimestampNegative() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(-1.0), "00:00:00")
    }

    func testFormatTimestampInfinity() {
        XCTAssertEqual(OutputRenderer.formatTimestamp(.infinity), "00:00:00")
    }

    // MARK: - formatTimestampWithMillis

    func testFormatTimestampWithMillisZeroComma() {
        XCTAssertEqual(OutputRenderer.formatTimestampWithMillis(0.0, separator: ","), "00:00:00,000")
    }

    func testFormatTimestampWithMillisZeroDot() {
        XCTAssertEqual(OutputRenderer.formatTimestampWithMillis(0.0, separator: "."), "00:00:00.000")
    }

    func testFormatTimestampWithMillisPrecision() {
        XCTAssertEqual(OutputRenderer.formatTimestampWithMillis(2.5, separator: ","), "00:00:02,500")
    }

    func testFormatTimestampWithMillisRounds() {
        XCTAssertEqual(OutputRenderer.formatTimestampWithMillis(1.9999, separator: ","), "00:00:02,000")
    }

    func testFormatTimestampWithMillisLarge() {
        XCTAssertEqual(OutputRenderer.formatTimestampWithMillis(3723.456, separator: ","), "01:02:03,456")
    }

    // MARK: - renderPlainText

    func testPlainTextJoined() {
        let result = OutputRenderer.renderPlainText(Self.sampleSegments)
        XCTAssertEqual(result, "Hello world Goodbye")
    }

    func testPlainTextTrimming() {
        let result = OutputRenderer.renderPlainText(Self.singleSegment)
        XCTAssertEqual(result, "Hello")
    }

    func testPlainTextEmpty() {
        XCTAssertEqual(OutputRenderer.renderPlainText([]), "")
    }

    // MARK: - renderTimestampedText

    func testTimestampedTextFormat() {
        let result = OutputRenderer.renderTimestampedText(Self.sampleSegments)
        let expected = "[00:00:00 --> 00:00:02] Hello world\n[00:00:02 --> 00:00:05] Goodbye"
        XCTAssertEqual(result, expected)
    }

    func testTimestampedTextEmpty() {
        XCTAssertEqual(OutputRenderer.renderTimestampedText([]), "")
    }

    // MARK: - renderSRT

    func testSRTFormat() {
        let result = OutputRenderer.renderSRT(Self.sampleSegments)
        let expected = "1\n00:00:00,000 --> 00:00:02,500\nHello world\n\n2\n00:00:02,500 --> 00:00:05,000\nGoodbye"
        XCTAssertEqual(result, expected)
    }

    func testSRTUsesComma() {
        let result = OutputRenderer.renderSRT(Self.sampleSegments)
        XCTAssertTrue(result.contains(","))
        XCTAssertFalse(result.contains("00:00:00."))
    }

    func testSRTEmpty() {
        XCTAssertEqual(OutputRenderer.renderSRT([]), "")
    }

    // MARK: - renderVTT

    func testVTTFormat() {
        let result = OutputRenderer.renderVTT(Self.sampleSegments)
        let expected = "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nHello world\n\n00:00:02.500 --> 00:00:05.000\nGoodbye"
        XCTAssertEqual(result, expected)
    }

    func testVTTHeader() {
        let result = OutputRenderer.renderVTT(Self.sampleSegments)
        XCTAssertTrue(result.hasPrefix("WEBVTT"))
    }

    func testVTTUsesDot() {
        let result = OutputRenderer.renderVTT(Self.sampleSegments)
        XCTAssertTrue(result.contains("00:00:00.000"))
    }

    func testVTTEmpty() {
        XCTAssertEqual(OutputRenderer.renderVTT([]), "WEBVTT")
    }

    // MARK: - renderJSON

    func testJSONContainsFields() {
        let result = OutputRenderer.renderJSON(Self.sampleSegments)
        XCTAssertTrue(result.contains("\"text\""))
        XCTAssertTrue(result.contains("\"segments\""))
        XCTAssertTrue(result.contains("Hello world"))
    }

    func testJSONValid() {
        let result = OutputRenderer.renderJSON(Self.sampleSegments)
        let data = result.data(using: .utf8)!
        let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertNotNil(parsed)
        XCTAssertEqual(parsed?["text"] as? String, "Hello world Goodbye")
    }

    // MARK: - renderOutputText dispatcher

    func testDispatcherTxtWithTimestamps() {
        let result = OutputRenderer.renderOutputText(Self.sampleSegments, format: .txt, includeTimestamps: true)
        XCTAssertTrue(result.contains("[00:00:00 --> 00:00:02]"))
    }

    func testDispatcherTxtWithoutTimestamps() {
        let result = OutputRenderer.renderOutputText(Self.sampleSegments, format: .txt, includeTimestamps: false)
        XCTAssertEqual(result, "Hello world Goodbye")
    }

    func testDispatcherSRT() {
        let result = OutputRenderer.renderOutputText(Self.sampleSegments, format: .srt)
        XCTAssertTrue(result.hasPrefix("1\n"))
    }

    func testDispatcherVTT() {
        let result = OutputRenderer.renderOutputText(Self.sampleSegments, format: .vtt)
        XCTAssertTrue(result.hasPrefix("WEBVTT"))
    }

    func testDispatcherJSON() {
        let result = OutputRenderer.renderOutputText(Self.sampleSegments, format: .json)
        XCTAssertTrue(result.contains("\"segments\""))
    }

    // MARK: - Collision-safe output paths

    func testOutputPathFirstOccurrence() {
        let url = OutputRenderer.buildOutputFilePath(directory: URL(filePath: "/tmp"), stem: "video", format: .txt)
        XCTAssertEqual(url.lastPathComponent, "video_transcription.txt")
    }

    func testOutputPathSecondOccurrence() {
        let url = OutputRenderer.buildOutputFilePath(directory: URL(filePath: "/tmp"), stem: "video", format: .txt, occurrence: 2)
        XCTAssertEqual(url.lastPathComponent, "video_transcription_2.txt")
    }

    func testOutputPathThirdOccurrenceSRT() {
        let url = OutputRenderer.buildOutputFilePath(directory: URL(filePath: "/tmp"), stem: "audio", format: .srt, occurrence: 3)
        XCTAssertEqual(url.lastPathComponent, "audio_transcription_3.srt")
    }
}
